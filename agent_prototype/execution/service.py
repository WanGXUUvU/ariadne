"""运行编排门面。

职责：
- 组装一次 run 所需的协作者。
- 驱动同步运行、流式运行和取消收尾。
- 将 child agent 调度和 trace 查询委托给专用服务。

上游：
- API routes

下游：
- RuntimeContextFactory
- AgentRunner / StreamRunSession
- RunPersistenceService / TraceQueryService / ChildAgentDispatcher

不负责：
- 不直接读取低层配置细节。
- 不自己反序列化 trace 事件。
- 不自己维护 child agent 线程状态。
"""

import uuid
from typing import AsyncIterator, Optional

# ── 第三方库 ──────────────────────────────────────────────────────────────────
from sqlalchemy.orm import Session

# ── 本地模块 ──────────────────────────────────────────────────────────────────
from agent_prototype.observation.tool_run_observer import ToolRunObserver
from agent_prototype.security.approval.store import SqliteApprovalStore
from agent_prototype.memory.session.store import SqliteSessionStore
from agent_prototype.memory.run.store import SqliteRunStore
from agent_prototype.tools.registry import build_run_registry
from agent_prototype.execution.persistence.types import (
    AgentInput,
    AgentOutput,
    RunFinalizationInput,
    RunFinalStatus,
)
from agent_prototype.execution.runtime.agent_runtime import AgentRunner
from agent_prototype.execution.runtime.vfs import RunVfsRegistry
from agent_prototype.execution.child_agent_dispatcher import ChildAgentDispatcher
from agent_prototype.execution.persistence.service import RunPersistenceService
from agent_prototype.execution.streaming.stream_run_session import StreamRunSession
from agent_prototype.execution.runtime_context_factory import RuntimeContextFactory
from agent_prototype.execution.trace_query_service import TraceQueryService


class RunService:
    """运行主链路的应用层门面。"""

    def __init__(self, db: Session):
        """使用当前 DB session 装配运行期协作者。"""
        self.db = db
        self.store = SqliteSessionStore(db)
        self._run_store = SqliteRunStore(db)
        self.approval_store = SqliteApprovalStore(db)
        self.persist = RunPersistenceService(db)
        self.context_factory = RuntimeContextFactory(db)
        self.child_dispatcher = ChildAgentDispatcher(db)
        self.trace_query = TraceQueryService(db, self._run_store)

    def _build_agent_runner(self, ctx, run_id: str, agent_input: AgentInput) -> AgentRunner:
        """基于运行物料和协作者构造 AgentRunner。"""
        return AgentRunner(
            state=ctx.state,
            definition=ctx.definition,
            allow_tool_names=ctx.definition.tool_names,
            model_adapter=ctx.adapter,
            tool_registry=build_run_registry(
                child_dispatcher=self.child_dispatcher.make_child_dispatcher(
                    run_id, agent_input.session_id
                ),
                status_checker=self.child_dispatcher.make_status_checker(),
                child_waiter=self.child_dispatcher.make_child_waiter(),
            ),
            approval_policy=ctx.approval_policy,
        )

    # ── 公开方法 ──────────────────────────────────────────────────────────────

    def run_agent(self, agent_input: AgentInput) -> AgentOutput:
        """执行一次同步 run，并在结束后持久化结果。"""
        run_id = uuid.uuid4().hex
        RunVfsRegistry.create(run_id)

        try:
            ctx = self.context_factory.build(agent_input)
            agent = self._build_agent_runner(ctx, run_id, agent_input)

            output = agent.run(agent_input, run_id=run_id)
            output.state.agent_name = ctx.effective_agent_name
            metadata = self.persist.finalize_run(
                RunFinalizationInput(
                    session_id=agent_input.session_id,
                    run_id=run_id,
                    status=RunFinalStatus.COMPLETED,
                    user_input=agent_input.user_input,
                    partial_reply=output.reply,
                    agent_name=ctx.effective_agent_name,
                    skill_name=agent_input.skill_name,
                    events=output.events,
                    state=output.state,
                    usage=output.usage,
                    session_type=ctx.session_type,
                )
            )
            return output.model_copy(
                update={"metadata": metadata},
            )
        except Exception:
            RunVfsRegistry.discard(run_id)
            raise

    async def async_stream_agent(self, agent_input: AgentInput) -> AsyncIterator[str]:
        """执行一次流式 run，逐帧产出 SSE 数据。"""
        run_id = uuid.uuid4().hex
        RunVfsRegistry.create(run_id)

        try:
            ctx = self.context_factory.build(agent_input)
            observer = ToolRunObserver(
                self.db,
                self._run_store,
                self.approval_store,
                agent_input.session_id,
                run_id=run_id,
                agent_input=agent_input,
            )
            agent = self._build_agent_runner(ctx, run_id, agent_input)

            async for frame in StreamRunSession(
                ctx,
                observer,
                agent,
                run_id,
                agent_input,
                self.persist,
            ).run():
                yield frame
        except Exception:
            RunVfsRegistry.discard(run_id)
            raise

    def finalize_run(
        self,
        session_id: str,
        run_id: str,
        user_input: str,
        partial_reply: str,
        agent_name: Optional[str],
        skill_name: Optional[str],
    ) -> dict:
        """保存被中止 run 的当前状态。"""
        self.persist.finalize_run(
            RunFinalizationInput(
                session_id=session_id,
                run_id=run_id,
                status=RunFinalStatus.CANCELLED,
                user_input=user_input,
                partial_reply=partial_reply,
                agent_name=agent_name,
                skill_name=skill_name,
            )
        )
        return {"ok": True}

    def get_run_detail(self, session_id: str, run_id: str):
        """返回某次 run 的回复和工具调用详情。"""
        return self.persist.get_run_detail(session_id, run_id)

    def get_child_run_status(self, run_id: str) -> dict:
        """查询单个子 Agent 的运行状态。"""
        return self.child_dispatcher.get_child_run_status(run_id)

    def get_session_trace(self, session_id: str, run_id: Optional[str] = None):
        """读取会话 trace；可按 run_id 过滤。"""
        return self.trace_query.get_session_trace(session_id, run_id=run_id)
