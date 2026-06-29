"""派发并执行子 Agent。"""

from concurrent.futures import Future
from concurrent.futures import ThreadPoolExecutor
import uuid
from typing import Callable

from backend.agent.types import AgentDefinition
from backend.run.types import RunInput, RunOutput
from backend.agent_loop.loop import AgentLoop
from backend.run.lifecycle import persist_run_event, finalize_run_execution
from backend.agent_loop.types import RunState
from backend.run.types import RunFinalStatus
from backend.run.runtime.vfs import RunVfsRegistry
from backend.run.setup import build_model_adapter
from backend.infra.db.engine import SessionLocal
from backend.infra.db.orm_models import SessionRunRecord
from backend.tools.build_registry import build_run_registry

# 进程级线程池，只创建一次。max_workers 控制并发子 Agent 上限。
_executor = ThreadPoolExecutor(
    max_workers=8,
    thread_name_prefix="child_agent",
)

# child_run_id → Future，进程级内存，重启后清空
_global_futures: dict = {}


def create_child_launcher(
    parent_run_id: str,
    session_id: str,
) -> Callable[[str, str], str]:
    """构造子 Agent 派发回调。"""

    def child_dispatcher(task: str, agent_name: str = "子Agent") -> str:
        child_run_id = uuid.uuid4().hex
        future = _executor.submit(
            execute_child_run,
            task=task,
            child_run_id=child_run_id,
            parent_run_id=parent_run_id,
            session_id=session_id,
            agent_name=agent_name,
        )
        _global_futures[child_run_id] = future
        return child_run_id

    return child_dispatcher


def create_child_status_checker() -> Callable[[list[str]], dict]:
    """构造批量查询子 Agent 状态的回调。"""

    def status_checker(child_run_ids: list[str]) -> dict:
        result = {}
        for run_id in child_run_ids:
            if run_id not in _global_futures:
                result[run_id] = {"status": "not_found"}
                continue

            future: Future[RunOutput] = _global_futures[run_id]
            if future.done():
                if future.exception():
                    result[run_id] = {
                        "status": "error",
                        "error": str(future.exception()),
                    }
                else:
                    result[run_id] = {
                        "status": "done",
                        "reply": future.result().reply,
                    }
            else:
                result[run_id] = {"status": "running"}
        return result

    return status_checker


def create_child_waiter() -> Callable[[str], str]:
    """构造阻塞等待单个子 Agent 完成的回调。"""

    def child_waiter(child_run_id: str) -> str:
        future = _global_futures.get(child_run_id)
        if future is None:
            raise LookupError(f"child_run_id {child_run_id} not found")
        output = future.result(timeout=120)
        return output.reply

    return child_waiter


def get_child_run_status(run_id: str) -> dict:
    """查询单个子 Agent 的运行状态。"""
    future = _global_futures.get(run_id)
    if future is None:
        return {"status": "not_found", "reply": None, "error": None}
    if not future.done():
        return {"status": "running", "reply": None, "error": None}

    exc = future.exception()
    if exc:
        return {"status": "error", "reply": None, "error": str(exc)}

    result = future.result()
    del _global_futures[run_id]
    return {"status": "done", "reply": result.reply, "error": None}


def execute_child_run(
    task: str,
    child_run_id: str,
    parent_run_id: str,
    session_id: str,
    agent_name: str = "子Agent",
):
    """在线程池中执行单个子 Agent 并落库结果。"""
    db = SessionLocal()
    RunVfsRegistry.create(child_run_id)
    try:
        from backend.infra.db.orm_models import SessionRecord

        session_rec = (
            db.query(SessionRecord)
            .filter(SessionRecord.session_id == session_id)
            .first()
        )
        workspace_path = None
        if session_rec:
            path_val = getattr(session_rec, "workspace_path", None)
            if isinstance(path_val, str):
                workspace_path = path_val

        adapter = build_model_adapter(
            db=db,
            session_id=session_id,
        )
        child_state = RunState()
        definition = AgentDefinition(
            id=child_run_id,
            name=agent_name,
        )
        agent_runner = AgentLoop(
            state=child_state,
            agent_profile=definition,
            model_adapter=adapter,
            tool_registry=build_run_registry(
                child_dispatcher=create_child_launcher(
                    parent_run_id=child_run_id,
                    session_id=session_id,
                ),
                status_checker=create_child_status_checker(),
                child_waiter=create_child_waiter(),
            ),
            vfs_provider=RunVfsRegistry.get,
        )
        run_input = RunInput(
            session_id=session_id,
            user_input=task,
            workspace_path=workspace_path,
        )
        output = agent_runner.run_sync(
            run_input=run_input,
            run_id=child_run_id,
        )

        active_tool_calls = {}
        for event in output.events:
            persist_run_event(
                db=db,
                run_id=child_run_id,
                event=event,
                session_id=session_id,
                loop_messages=agent_runner.state.messages,
                active_tool_calls=active_tool_calls,
            )

        finalize_run_execution(
            db=db,
            run_id=child_run_id,
            session_id=session_id,
            user_input=task,
            status=RunFinalStatus.COMPLETED,
            events=output.events,
            reply=output.reply,
            effective_agent_name=agent_name,
            loop_state=agent_runner.state,
            last_usage=getattr(agent_runner, "last_usage", None),
            is_resume=False,
            owns_session=False,
        )
        result = output

        # 子 run 的主记录和事件已经由统一 finalization 写入，这里只补父子关联。
        run_record = (
            db.query(SessionRunRecord)
            .filter(SessionRunRecord.run_id == child_run_id)
            .first()
        )
        if run_record is None:
            raise LookupError(
                f"child run {child_run_id} not found after finalization"
            )
        run_record.parent_run_id = parent_run_id
        db.commit()
        return result
    except Exception:
        db.rollback()
        RunVfsRegistry.discard(child_run_id)
        raise
    finally:
        db.close()
