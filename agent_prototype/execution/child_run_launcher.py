"""子 Agent 调度服务。

职责：
- 构造 child dispatcher / status checker / waiter 回调。
- 管理 _global_futures 生命周期。
- 执行后台子 Agent worker。

不负责：
- 不处理主 run 上下文装配。
- 不处理 trace 查询。
- 不感知 HTTP/SSE。
"""

from concurrent.futures import Future
import uuid
from typing import Callable

from sqlalchemy.orm import Session

from agent_prototype.agent.types import AgentDefinition
from agent_prototype.execution.persistence.run_recorder import RunRecorder
from agent_prototype.execution.persistence.types import RunInput, RunContext
from agent_prototype.execution.runtime.agent_executor import _executor, _global_futures
from agent_prototype.execution.runtime.agent_runner import AgentRunner
from agent_prototype.execution.runtime.run_lifecycle import (
    RunLifecycleParams,
    RunLifecycleResultItem,
    RunLifecycle,
)
from agent_prototype.execution.runtime.types import RunState
from agent_prototype.execution.runtime.vfs import RunVfsRegistry
from agent_prototype.execution.run_context_factory import RunContextFactory
from agent_prototype.infra.db.engine import SessionLocal
from agent_prototype.infra.db.orm_models import SessionRunRecord
from agent_prototype.tools.registry import build_run_registry
from agent_prototype.security.policy.types import ApprovalPolicy


class ChildRunLauncher:
    """子 Agent 线程调度与状态查询服务。"""

    def __init__(self, db: Session):
        self.db = db

    def create_launcher(
        self,
        parent_run_id: str,
        session_id: str,
    ) -> Callable[[str, str], str]:
        """构造子 Agent 派发回调。"""

        def child_dispatcher(task: str, agent_name: str = "子Agent") -> str:
            child_run_id = uuid.uuid4().hex
            future = _executor.submit(
                self._execute_child,
                task=task,
                child_run_id=child_run_id,
                parent_run_id=parent_run_id,
                session_id=session_id,
                agent_name=agent_name,
            )
            _global_futures[child_run_id] = future
            return child_run_id

        return child_dispatcher

    def create_status_checker(self) -> Callable[[list[str]], dict]:
        """构造批量查询子 Agent 状态的回调。"""

        def status_checker(child_run_ids: list[str]) -> dict:
            result = {}
            for run_id in child_run_ids:
                if run_id not in _global_futures:
                    result[run_id] = {"status": "not_found"}
                    continue

                future: Future[RunLifecycleResultItem] = _global_futures[run_id]
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

    def create_waiter(self) -> Callable[[str], str]:
        """构造阻塞等待单个子 Agent 完成的回调。"""

        def child_waiter(child_run_id: str) -> str:
            future = _global_futures.get(child_run_id)
            if future is None:
                raise LookupError(f"child_run_id {child_run_id} not found")
            output = future.result(timeout=120)
            return output.reply

        return child_waiter

    def get_child_run_status(self, run_id: str) -> dict:
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

    def _execute_child(
        self,
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
            from agent_prototype.infra.db.orm_models import SessionRecord

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

            adapter = RunContextFactory(db).create_adapter(session_id)
            child_state = RunState()
            definition = AgentDefinition(id=child_run_id, name=agent_name)
            agent_runner = AgentRunner(
                state=child_state,
                agent_profile=definition,
                model_adapter=adapter,
                tool_registry=build_run_registry(
                    child_dispatcher=self.create_launcher(child_run_id, session_id),
                    status_checker=self.create_status_checker(),
                    child_waiter=self.create_waiter(),
                ),
            )
            run_input = RunInput(
                session_id=session_id,
                user_input=task,
                workspace_path=workspace_path,
            )
            ctx = RunContext(
                state=child_state,
                agent_profile=definition,
                adapter=adapter,
                approval_policy=ApprovalPolicy.NEVER,
                effective_agent_name=agent_name,
                workspace_path=workspace_path or "",
                session_type="coding",
            )
            result = RunLifecycle(
                RunLifecycleParams(
                    ctx=ctx,
                    agent_runner=agent_runner,
                    recorder=RunRecorder(db),
                    run_input=run_input,
                    run_id=child_run_id,
                    owns_session=False,
                )
            ).execute_sync()

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
