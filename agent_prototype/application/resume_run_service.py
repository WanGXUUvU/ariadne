from typing import AsyncIterator
from sqlalchemy.orm import Session

from ..core.schemas import AgentState, AgentInput, AgentEvent, ChatMessage, StreamFrame, ToolResult
from ..storage.stores.approval_store import SqliteApprovalStore
from ..storage.stores.session_store import SqliteSessionStore
from ..storage.models import SessionRunRecord
from ..tools.tool_registry import build_run_registry
from ..runtime.agent_runtime import Agent
from ..model.openai_adapter import ChatCompletionsAdapter
from .run_service import _executor, _global_futures, _sse_frame, RUN_MODEL
from .agent_definition_service import load_agent_definition_service


async def resume_run_service(approval_id: str, db: Session, rejected: bool = False):
    approval_store = SqliteApprovalStore(db)
    store = SqliteSessionStore(db)

    approval = approval_store.get(approval_id)
    messages = approval_store.restore_messages(approval)

    event_index = approval.event_index
    state = AgentState(messages=messages)

    run_record = db.query(SessionRunRecord).filter(
        SessionRunRecord.run_id == approval.run_id
    ).first()
    agent_name = run_record.agent_name if run_record else "default"
    defintion = load_agent_definition_service(agent_name, db)
    tool_registry = build_run_registry(
        parent_run_id=approval.run_id,
        session_id=approval.session_id,
        executor=_executor,
        futures=_global_futures,
    )

    if rejected:
        content = "[TOOL_REJECTED] 用户拒绝了此工具调用"
        tr = ToolResult(ok=False, content=content)
    else:
        tool_result = tool_registry.execute_tool_call(approval.tool_name, approval.arguments)
        content = tool_result.content if tool_result.ok else f"[TOOL_ERROR] {tool_result.error.message}"
        tr = ToolResult(ok=tool_result.ok, content=content)

    # 构造 tool_result AgentEvent，补充审批后的工具执行结果
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

    agent=Agent(
        state=state,
        definition=defintion,
        allow_tool_names=defintion.tool_names,
        model_adapter=ChatCompletionsAdapter(model=RUN_MODEL),
        tool_registry=tool_registry,
    )
    agent_input=AgentInput.model_construct(
        session_id=approval.session_id,
        user_input="",
        agent_name=None,
        skill_name=None,
    )
    partial_reply = ""

    yield _sse_frame(StreamFrame(type="resume", data={"run_id": approval.run_id}))
    # 立即发送 tool_result 事件，让前端 timeline 看到工具执行结果
    yield _sse_frame(StreamFrame(type="agent_event", data=tool_result_event.model_dump()))

    events: list[AgentEvent] = [tool_result_event]
    async for item in agent.async_stream_run(
        agent_input,
        skip_user_message=True,
        event_index=event_index,
    ):
        if isinstance(item, str):
            partial_reply += item
            yield _sse_frame(StreamFrame(type="delta", data={"content": item}))
        elif isinstance(item, AgentEvent):
            events.append(item)
            yield _sse_frame(StreamFrame(type="agent_event", data=item.model_dump()))

    # 5. 追加 trace + 更新状态
    store.append_run_events(
        run_id=approval.run_id,
        new_events=events,
        final_reply=partial_reply,
    )
    store.update_run_status(run_id=approval.run_id, status="completed")
    # 同步更新 session_records 的 state_json（agent 继续运行后 state 已更新）
    store.upsert_session_snapshot(
        session_id=approval.session_id,
        state=agent.state,
    )
    db.commit()

    yield _sse_frame(StreamFrame(
        type="end",
        data={"reply": partial_reply, "run_id": approval.run_id, "state": agent.state.model_dump()},
    ))