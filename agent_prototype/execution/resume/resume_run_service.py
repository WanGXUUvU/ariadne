"""审批恢复运行编排层。

职责：
- 根据 approval_id 重建 Agent 上下文（恢复消息 + 加载定义 + 构建 Adapter）
- 执行审批结果（通过 / 拒绝），拼装工具结果事件
- 拉起 Agent 继续流式运转，yield SSE 帧
- 运行结束后委托 RunPersistenceService 落库

不负责：感知 HTTP 协议、直接操作 DB 模型。
上游：approval_routes.py
下游：RunContextBuilder.build_adapter / RunPersistenceService.save_resumed
"""

# ── 标准库 ────────────────────────────────────────────────────────────────────
from typing import AsyncIterator

# ── 第三方库 ──────────────────────────────────────────────────────────────────
from sqlalchemy.orm import Session

# ── 本地模块 ──────────────────────────────────────────────────────────────────
from agent_prototype.api.dto.schemas import (
    AgentEvent, AgentInput, AgentState, ChatMessage, StreamFrame, ToolResult,
)
from agent_prototype.memory.session.store import SqliteSessionStore
from agent_prototype.infra.db.orm_models import SessionRunRecord
from agent_prototype.security.approval.store import SqliteApprovalStore
from agent_prototype.tools.registry import build_run_registry
from agent_prototype.execution.runtime.agent_runtime import AgentRunner
from agent_prototype.execution.runtime.agent_executor import _executor, _global_futures
from agent_prototype.execution.streaming.sse import _sse_frame
from agent_prototype.agent.definition_service import AgentDefinitionService
from agent_prototype.execution.persistence.run_context_builder import RunContextBuilder
from agent_prototype.execution.persistence.run_persistence import RunPersistenceService


class ResumeRunService:
    """审批恢复运行编排类。"""

    def __init__(self, db: Session):
        self.db             = db
        self.approval_store = SqliteApprovalStore(db)
        self.persist        = RunPersistenceService(db)
        self.session_store  = SqliteSessionStore(db)

    async def resume_run(self, approval_id: str, rejected: bool = False) -> AsyncIterator[str]:
        """执行审批结果并恢复 Agent 流式运转。

        :param approval_id: 待审批记录 ID
        :param rejected:    用户是否拒绝本次工具调用
        """
        approval  = self.approval_store.get(approval_id)
        messages  = self.approval_store.restore_messages(approval)
        state     = AgentState(messages=messages)

        # ── 加载 Agent 定义 ───────────────────────────────────────────────────
        run_record = self.db.query(SessionRunRecord).filter(
            SessionRunRecord.run_id == approval.run_id
        ).first()
        session_id=run_record.session_id
        agent_name = run_record.agent_name if run_record else "default"
        definition = AgentDefinitionService(self.db).load_definition(agent_name)

        # ── 构建 tool registry & adapter ─────────────────────────────────────
        tool_registry = build_run_registry(
            parent_run_id=approval.run_id,
            session_id=approval.session_id,
            executor=_executor,
            futures=_global_futures,
        )
        model_adapter = RunContextBuilder(self.db).build_adapter(approval.session_id)

        # ── 执行审批结果，构造工具结果事件 ────────────────────────────────────
        if rejected:
            content = "[TOOL_REJECTED] 用户拒绝了此工具调用"
            tr = ToolResult(ok=False, content=content)
        else:
            tool_result = tool_registry.execute_tool_call(approval.tool_name, approval.arguments)
            content = tool_result.content if tool_result.ok else f"[TOOL_ERROR] {tool_result.error.message}"
            tr = ToolResult(ok=tool_result.ok, content=content)

        event_index = approval.event_index
        tool_result_event = AgentEvent(
            index=event_index,
            type="tool_result",
            content=content,
            tool_name=approval.tool_name,
            tool_call_id=approval.tool_call_id,
            tool_result=tr,
        )
        event_index += 1
        state.messages.append(ChatMessage(role="tool", tool_call_id=approval.tool_call_id, content=content))

        # ── 构造 AgentRunner，继续流式运转 ────────────────────────────────────
        agent = AgentRunner(
            state=state,
            definition=definition,
            allow_tool_names=definition.tool_names,
            model_adapter=model_adapter,
            tool_registry=tool_registry,
        )
        agent_input = AgentInput.model_construct(
            session_id=approval.session_id,
            user_input="",
            agent_name=None,
            skill_name=None,
        )

        yield _sse_frame(StreamFrame(type="resume", data={"run_id": approval.run_id}))
        yield _sse_frame(StreamFrame(type="agent_event", data=tool_result_event.model_dump()))

        partial_reply = ""
        events: list[AgentEvent] = [tool_result_event]
        workspace_path = self.session_store.read_session_record(approval.session_id).workspace_path
        async for item in agent.async_stream_run(
            agent_input,
            skip_user_message=True,
            event_index=event_index,
            run_id=approval.run_id,
            workspace_path=workspace_path,
        ):
            if isinstance(item, str):
                partial_reply += item
                yield _sse_frame(StreamFrame(type="delta", data={"content": item}))
            elif isinstance(item, AgentEvent):
                events.append(item)
                yield _sse_frame(StreamFrame(type="agent_event", data=item.model_dump()))

        # ── 落库 ─────────────────────────────────────────────────────────────
        self.persist.save_resumed(
            run_id=approval.run_id,
            session_id=approval.session_id,
            events=events,
            partial_reply=partial_reply,
            agent_state=agent.state,
        )

        yield _sse_frame(StreamFrame(
            type="end",
            data={"reply": partial_reply, "run_id": approval.run_id, "state": agent.state.model_dump()},
        ))
