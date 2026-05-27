"""
[九层模型 - L8 执行引擎层 (Execution Layer)]

文件职责：
- 充当运行时核心业务流编排与引擎层（RunService）。
- 整合 RunContext 构建、AgentRunner 同步/流式运行驱动、以及物理持久化落库。
- 构建并闭包包装三个“三纯回调函数”（派发器、查询器、等待器），将其动态注入至 ToolRegistry，从而完美实现工具层与执行引擎的解耦。
- 实现线程安全的异步后台工作器（_run_child_worker）来调度物理子任务线程。

上游依赖：L10 接口层 (GET/POST 路由控制器)。
下游依赖：L8 上下文构建器 (run_context_builder.py)、L8 运行载体 (agent_runtime.py)、L3 工具注册中心 (ToolRegistry)。
"""
# ── 标准库 ────────────────────────────────────────────────────────────────────
import uuid
from typing import AsyncIterator, Optional, Callable

# ── 第三方库 ──────────────────────────────────────────────────────────────────
from sqlalchemy.orm import Session

# ── 本地模块 ──────────────────────────────────────────────────────────────────
from agent_prototype.observation.hooks.tool_run_observer import ToolRunObserver
from agent_prototype.security.approval.store import SqliteApprovalStore
from agent_prototype.memory.session.store import SqliteSessionStore
from agent_prototype.model.types.model_types import ModelStreamEvent
from agent_prototype.tools.registry import build_run_registry
from agent_prototype.api.dto.schemas import (
    AgentEvent, AgentInput, AgentOutput, AgentState,
    RunMetadata, StreamFrame,
)
from agent_prototype.execution.runtime.agent_runtime import AgentRunner
from agent_prototype.execution.runtime.agent_executor import _executor, _global_futures
from .run_context_builder import RunContextBuilder
from .run_persistence import RunPersistenceService
from agent_prototype.execution.streaming.stream_run_session import StreamRunSession


class RunService:
    """运行时核心应用服务类 (RunService)

    采用极致的 OOP 设计，通过构造注入 Session 依赖，生命周期契合单元事务。
    """

    def __init__(self, db: Session):
        self.db            = db
        self.store         = SqliteSessionStore(db)
        self.approval_store = SqliteApprovalStore(db)
        self.persist       = RunPersistenceService(db)

    # ── 私有辅助 ──────────────────────────────────────────────────────────────

    def _make_child_dispatcher(self, parent_run_id: str, session_id: str) -> Callable[[str, str], str]:
        """构造子智能体派发器闭包，将线程提交、ID 生成及落库操作限制在 L8 内部"""
        def child_dispatcher(task: str, agent_name: str = "子Agent") -> str:
            child_run_id = uuid.uuid4().hex
            
            # 将异步运行子 Agent 任务提交至全局线程池中执行
            future = _executor.submit(
                self._run_child_worker,
                task=task,
                child_run_id=child_run_id,
                parent_run_id=parent_run_id,
                session_id=session_id,
                agent_name=agent_name,
            )
            _global_futures[child_run_id] = future
            return child_run_id
        return child_dispatcher

    def _make_status_checker(self) -> Callable[[list[str]], dict]:
        """构造非阻塞状态查询器闭包，封装对全局 Future 状态的获取逻辑"""
        def status_checker(child_run_ids: list[str]) -> dict:
            result = {}
            for run_id in child_run_ids:
                if run_id not in _global_futures:
                    result[run_id] = {"status": "not_found"}
                    continue

                f = _global_futures[run_id]
                if f.done():
                    if f.exception():
                        result[run_id] = {"status": "error", "error": str(f.exception())}
                    else:
                        result[run_id] = {"status": "done", "reply": f.result().reply}
                else:
                    result[run_id] = {"status": "running"}
            return result
        return status_checker

    def _make_child_waiter(self) -> Callable[[str], str]:
        """构造阻塞等待器闭包，控制超时及结果提取"""
        def child_waiter(child_run_id: str) -> str:
            f = _global_futures.get(child_run_id)
            if f is None:
                raise LookupError(f"child_run_id {child_run_id} not found")
            
            # 这里调用 result(timeout=120) 会阻塞等待 120s，超时抛出 TimeoutError，失败则抛出对应异常
            output = f.result(timeout=120)
            return output.reply
        return child_waiter

    def _run_child_worker(
        self,
        task: str,
        child_run_id: str,
        parent_run_id: str,
        session_id: str,
        agent_name: str = "子Agent"
    ):
        """物理子智能体线程执行与落库的工作器方法"""
        from agent_prototype.infra.db.engine import SessionLocal
        from agent_prototype.agent.definition import AgentDefinition
        
        # ⚠️ 注意：子智能体运行于独立线程，必须使用单独的物理 DB Session
        db = SessionLocal()
        try:
            adapter = RunContextBuilder(db).build_adapter(session_id)
            child_state = AgentState()
            definition = AgentDefinition(id=child_run_id, name=agent_name)
            
            agent = AgentRunner(
                state=child_state,
                definition=definition,
                model_adapter=adapter,
                # 子 Agent 递归支持工具箱，并且同样采用闭包回调隔离依赖
                tool_registry=build_run_registry(
                    child_dispatcher=self._make_child_dispatcher(child_run_id, session_id),
                    status_checker=self._make_status_checker(),
                    child_waiter=self._make_child_waiter(),
                )
            )
            output = agent.run(AgentInput(
                session_id=session_id,
                user_input=task,
            ))

            # 📍 落库：子 Agent 的 run 记录 + 事件列表，挂在同一个 session 下
            store = SqliteSessionStore(db)
            store.create_child_run(
                parent_run_id=parent_run_id,
                session_id=session_id,
                run_id=child_run_id,
                agent_name=agent_name,
                user_input=task,
                reply=output.reply,
                events=output.events,
            )
            db.commit()
            return output
        except Exception as e:
            db.rollback()
            print(f"Failed to persist child run {child_run_id}: {e}")
            raise
        finally:
            db.close()

    def _build_agent_runner(self, ctx, run_id: str, agent_input: AgentInput) -> AgentRunner:
        """根据 RunContext 构造 AgentRunner，两个入口共用。"""
        return AgentRunner(
            state=ctx.state,
            definition=ctx.definition,
            allow_tool_names=ctx.definition.tool_names,
            model_adapter=ctx.adapter,
            # 核心解耦点：通过注入三个“三纯”回调将工具层与底座执行细节彻底解耦
            tool_registry=build_run_registry(
                child_dispatcher=self._make_child_dispatcher(run_id, agent_input.session_id),
                status_checker=self._make_status_checker(),
                child_waiter=self._make_child_waiter(),
            ),
            approval_policy=ctx.approval_policy,
        )

    # ── 公开方法 ──────────────────────────────────────────────────────────────

    def run_agent(self, agent_input: AgentInput) -> AgentOutput:
        """主入口：非流式同步驱动 Agent 运转"""
        run_id = uuid.uuid4().hex
        ctx = RunContextBuilder(self.db).build(agent_input)
        agent = self._build_agent_runner(ctx, run_id, agent_input)

        output = agent.run(agent_input)
        output.state.agent_name = ctx.effective_agent_name
        return self.persist.save_completed(
            agent_input=agent_input,
            output=output,
            effective_agent_name=ctx.effective_agent_name,
            run_id=run_id,
            usage=output.usage,
            session_type=ctx.session_type,
        )

    async def async_stream_agent(self, agent_input: AgentInput) -> AsyncIterator[str]:
        """异步 SSE 流式驱动 Agent 运转（支持高并发工具审批中断与 ToolCall 中间态落库）"""
        run_id   = uuid.uuid4().hex
        ctx      = RunContextBuilder(self.db).build(agent_input)
        observer = ToolRunObserver(self.db, self.store, self.approval_store,
                                    agent_input.session_id, run_id, agent_input)
        agent    = self._build_agent_runner(ctx, run_id, agent_input)
        async for frame in StreamRunSession(ctx, observer, agent, run_id, agent_input, self.persist).run():
            yield frame

    def finalize_run(
        self,
        session_id: str,
        run_id: str,
        user_input: str,
        partial_reply: str,
        agent_name: Optional[str],
        skill_name: Optional[str],
    ) -> dict:
        return self.persist.save_cancelled(
            session_id, run_id, user_input, partial_reply, agent_name, skill_name,
        )

    def get_run_detail(self, session_id: str, run_id: str):
        return self.persist.get_run_detail(session_id, run_id)
