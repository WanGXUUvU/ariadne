"""运行时业务编排层。

这个文件负责把多个底层组件串起来：
- 读取 / 更新 session 状态
- 选择 agent 定义
- 调用 Agent 执行
- 持久化 session 快照 and trace

这里是“业务流程”发生的地方，不直接暴露 HTTP，也不直接定义 ORM 表结构。
"""

# ── 标准库 ────────────────────────────────────────────────────────────────────
import uuid
from typing import AsyncIterator, Optional

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

    def _build_agent_runner(self, ctx, run_id: str, agent_input: AgentInput) -> AgentRunner:
        """根据 RunContext 构造 AgentRunner，两个入口共用。"""
        return AgentRunner(
            state=ctx.state,
            definition=ctx.definition,
            allow_tool_names=ctx.definition.tool_names,
            model_adapter=ctx.adapter,
            tool_registry=build_run_registry(
                parent_run_id=run_id,
                session_id=agent_input.session_id,
                executor=_executor,
                futures=_global_futures,
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

