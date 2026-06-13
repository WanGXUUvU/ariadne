"""运行编排门面。

职责：
- 组装一次 run 所需的协作者。
- 驱动同步运行、流式运行和取消收尾。
- 将 child agent 调度和 trace 查询委托给专用服务。

上游：
- API routes

下游：
- RunContextFactory
- AgentRunner / RunSSEBridge
- RunRecorder / TraceQueryService / ChildRunLauncher

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
from agent_prototype.observation.tool_tracer import ToolTracer
from agent_prototype.security.approval.store import SqliteApprovalStore
from agent_prototype.memory.session.store import SessionStore
from agent_prototype.memory.run.store import RunTraceStore
from agent_prototype.tools.registry import build_run_registry
from agent_prototype.execution.persistence.types import (
    RunInput,
    RunOutput,
    RunFinalizationInput,
    RunFinalStatus,
    RunMetadata,
)
from agent_prototype.execution.runtime.agent_runner import AgentRunner
from agent_prototype.execution.runtime.run_lifecycle import (
    RunLifecycleParams,
    RunLifecycle,
)
from agent_prototype.execution.runtime.vfs import RunVfsRegistry
from agent_prototype.execution.child_run_launcher import ChildRunLauncher
from agent_prototype.execution.persistence.run_recorder import RunRecorder
from agent_prototype.execution.streaming.sse_bridge import RunSSEBridge
from agent_prototype.execution.run_context_factory import RunContextFactory
from agent_prototype.execution.trace_query_service import TraceQueryService


class RunService:
    """运行主链路的应用层门面。"""

    def __init__(self, db: Session):
        """使用当前 DB session 装配运行期协作者。"""
        self.db = db
        self.store = SessionStore(db)
        self._run_store = RunTraceStore(db)
        self.approval_store = SqliteApprovalStore(db)
        self.persist = RunRecorder(db)
        self.context_factory = RunContextFactory(db)
        self.child_dispatcher = ChildRunLauncher(db)
        self.trace_query = TraceQueryService(db, self._run_store)

    def _create_agent_runner(self, ctx, run_id: str, run_input: RunInput) -> AgentRunner:
        """基于运行物料和协作者构造 AgentRunner。"""
        return AgentRunner(
            state=ctx.state,
            agent_profile=ctx.agent_profile,
            model_adapter=ctx.adapter,
            tool_registry=build_run_registry(
                child_dispatcher=self.child_dispatcher.create_launcher(
                    run_id, run_input.session_id
                ),
                status_checker=self.child_dispatcher.create_status_checker(),
                child_waiter=self.child_dispatcher.create_waiter(),
            ),
            approval_policy=ctx.approval_policy,
        )

    # ── 公开方法 ──────────────────────────────────────────────────────────────

    def run(self, run_input: RunInput) -> RunOutput:
        """执行一次同步 run，并在结束后持久化结果。"""
        run_id = uuid.uuid4().hex
        RunVfsRegistry.create(run_id)

        try:
            ctx = self.context_factory.assemble(run_input)
            agent_runner = self._create_agent_runner(ctx, run_id, run_input)

            result = RunLifecycle(
                RunLifecycleParams(
                    ctx=ctx,
                    agent_runner=agent_runner,
                    persist=self.persist,
                    run_input=run_input,
                    run_id=run_id,
                )
            ).execute_sync()
            result.state.agent_name = ctx.effective_agent_name
            return RunOutput(
                reply=result.reply_text,
                state=result.state,
                events=result.events,
                metadata=RunMetadata(
                    session_id=run_input.session_id,
                    run_id=run_id,
                    agent_name=ctx.effective_agent_name,
                ),
                usage=result.usage,
            )
        except Exception:
            RunVfsRegistry.discard(run_id)
            raise

    async def stream(self, run_input: RunInput) -> AsyncIterator[str]:
        """执行一次流式 run，逐帧产出 SSE 数据。"""
        run_id = uuid.uuid4().hex
        RunVfsRegistry.create(run_id)

        try:
            ctx = self.context_factory.assemble(run_input)
            observer = ToolTracer(
                self.db,
                self._run_store,
                self.approval_store,
                run_input.session_id,
                run_id=run_id,
                run_input=run_input,
            )
            agent_runner = self._create_agent_runner(ctx, run_id, run_input)

            async for frame in RunSSEBridge(
                ctx,
                observer,
                agent_runner,
                run_id,
                run_input,
                self.persist,
            ).stream():
                yield frame
        except Exception:
            RunVfsRegistry.discard(run_id)
            raise

    def cancel_run(
        self,
        session_id: str,
        run_id: str,
        user_input: str,
        reply_text: str,
        agent_name: Optional[str],
    ) -> dict:
        """保存被中止 run 的当前状态。"""
        self.persist.finalize_run(
            RunFinalizationInput(
                session_id=session_id,
                run_id=run_id,
                status=RunFinalStatus.CANCELLED,
                user_input=user_input,
                reply_text=reply_text,
                agent_name=agent_name,
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
