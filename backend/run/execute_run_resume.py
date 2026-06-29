"""恢复因审批暂停的运行流。"""

import asyncio
from typing import AsyncIterator, Optional

from sqlalchemy.orm import Session

from backend.run.types import (
    RunInput,
    RunFinalizationInput,
    RunFinalStatus,
)
from backend.approval.store import SqliteApprovalStore
from backend.agent import load_agent_definition
from backend.agent_loop.types import RunEvent
from backend.run.build_agent_loop import build_agent_loop, build_run_tool_registry
from backend.tools.result_types import ToolResult
from backend.core.types import ChatMessage
from backend.session.store import SessionStore
from backend.infra.db.orm_models import SessionRunRecord
from backend.security.middleware.base import MiddlewarePipeline, ToolCallContext
from backend.sandbox.middleware import SandboxMiddleware
from backend.run.lifecycle import (
    process_agent_stream,
    persist_run_event,
    finalize_run_execution,
)
from backend.run.runtime.sse import _sse_frame
from backend.run.runtime.recorder import RunRecorder
from backend.run.runtime.vfs import RunVfsRegistry
from backend.run.setup import (
    build_model_adapter,
    build_runtime_system_prompt_for_run,
    resolve_approval_policy,
)


async def execute_run_resume(
    *,
    db: Session,
    approval_id: str,
    rejected: bool = False,
    recorder: Optional[RunRecorder] = None,
    approval_store: Optional[SqliteApprovalStore] = None,
    session_store: Optional[SessionStore] = None,
) -> AsyncIterator[str]:
    """恢复一次因审批暂停的运行流，包含审批处理与智能体流式继续运转的完整过程。"""
    # 1. 读取暂停中的审批上下文
    store_approval = approval_store or SqliteApprovalStore(db)
    rec = recorder or RunRecorder(db)
    store_session = session_store or SessionStore(db)

    approval = store_approval.get(approval_id=approval_id)
    if approval is None:
        raise ValueError("Approval not found")

    state = store_session.read_session_state(
        session_id=approval.session_id,
    )
    if state is None:
        raise ValueError("Session state not found")

    batch_id = approval.batch_id or approval.run_id

    # 2. 解析本轮元数据与可复用协作者
    run_record = (
        db.query(SessionRunRecord)
        .filter(SessionRunRecord.run_id == approval.run_id)
        .first()
    )
    agent_name = run_record.agent_name if run_record else "default"
    session_record = store_session.load_record(
        session_id=approval.session_id,
    )
    agent_profile = load_agent_definition(
        db=db,
        agent_id=agent_name,
    )
    workspace_path = session_record.workspace_path if session_record else None
    tool_registry = build_run_tool_registry(
        run_id=approval.run_id,
        session_id=approval.session_id,
    )

    # 3. 应用审批结果并生成一个 tool_result 事件
    event_index = approval.event_index
    if rejected:
        content = "[TOOL_REJECTED] 用户拒绝了此工具调用"
        tr = ToolResult(ok=False, content=content)
    else:
        loop = asyncio.get_event_loop()
        pipeline = MiddlewarePipeline([SandboxMiddleware()])

        context = ToolCallContext(
            tool_name=approval.tool_name,
            tool_args=approval.arguments,
            tool_call_id=approval.tool_call_id,
            session_id=approval.session_id,
            run_id=approval.run_id,
            workspace_path=workspace_path,
            allow_tool_names=agent_profile.tool_names,
            vfs=RunVfsRegistry.get(approval.run_id),
        )

        async def terminal_execute_call() -> ToolResult:
            return await loop.run_in_executor(
                None,
                tool_registry.execute_tool_call,
                context.tool_name,
                context.tool_args,
                context,
            )

        tool_result = await pipeline.execute(context, terminal_execute_call)
        if tool_result.ok:
            content = tool_result.content
            tr = tool_result
        else:
            error_message = (
                tool_result.error.message if tool_result.error else "Tool failed"
            )
            content = f"[TOOL_ERROR] {error_message}"
            tr = tool_result.model_copy(update={"content": content})

    tool_result_event = RunEvent(
        index=event_index,
        type="tool_result",
        content=content,
        tool_name=approval.tool_name,
        tool_call_id=approval.tool_call_id,
        tool_result=tr,
    )
    event_index += 1
    state.messages.append(
        ChatMessage(
            role="tool", tool_call_id=approval.tool_call_id, content=content
        )
    )

    # 4. 这一批审批还没处理完则先暂停返回
    if not store_approval.is_batch_fully_resolved(batch_id=batch_id):
        next_pending = store_approval.get_next_pending_for_batch(batch_id=batch_id)
        rec.finalize_run(
            finalization=RunFinalizationInput(
                session_id=approval.session_id,
                run_id=approval.run_id,
                status=RunFinalStatus.PAUSED,
                user_input="",
                reply="",
                agent_name=agent_name,
                events=[tool_result_event],
                state=state,
                is_resume=True,
            )
        )
        yield _sse_frame("resume", {"run_id": approval.run_id})
        yield _sse_frame("run_event", tool_result_event.model_dump())
        yield _sse_frame(
            "paused",
            {
                "run_id": approval.run_id,
                "approval_id": next_pending.id if next_pending else None,
            },
        )
        return

    # 5. 模型恢复前先落下已解析的工具结果
    store_session.save_state(
        session_id=approval.session_id,
        state=state,
    )
    db.commit()

    yield _sse_frame("resume", {"run_id": approval.run_id})
    yield _sse_frame("run_event", tool_result_event.model_dump())

    # 6. 只有需要继续时才重建模型循环
    run_input = RunInput.model_construct(
        session_id=approval.session_id,
        user_input="",
        agent_name=None,
        skill_name=None,
    )
    approval_policy = resolve_approval_policy(
        record=session_record,
    )
    runtime_system_prompt = build_runtime_system_prompt_for_run(
        run_input=run_input,
        workspace_path=workspace_path,
        definition=agent_profile,
    )
    agent_runner = build_agent_loop(
        run_id=approval.run_id,
        session_id=approval.session_id,
        state=state,
        agent_profile=agent_profile,
        runtime_system_prompt=runtime_system_prompt,
        model_adapter=build_model_adapter(
            db=db,
            session_id=approval.session_id,
        ),
        approval_policy=approval_policy,
    )

    # 7. 继续暂停前的流并持久化恢复阶段事件
    raw_stream = agent_runner.stream(
        run_input=run_input,
        skip_user_message=True,
        event_index=event_index,
        run_id=approval.run_id,
        workspace_path=workspace_path,
    )

    reply_text = ""
    events = [tool_result_event]
    active_tool_calls = {}

    try:
        async for frame in process_agent_stream(
            raw_stream=raw_stream,
            event_index=event_index,
            initial_events=[tool_result_event],
        ):
            if frame["type"] == "run_event":
                event = RunEvent(**frame["data"])
                persist_run_event(
                    db=db,
                    run_id=approval.run_id,
                    event=event,
                    session_id=approval.session_id,
                    loop_messages=agent_runner.state.messages,
                    active_tool_calls=active_tool_calls,
                )
                if not event.transient:
                    events.append(event)
            elif frame["type"] == "delta":
                reply_text += frame["data"]["content"]

            if frame["type"] == "paused":
                next_pending = store_approval.get_next_pending_for_batch(
                    batch_id=batch_id,
                )
                frame["data"]["approval_id"] = next_pending.id if next_pending else None

            yield _sse_frame(frame["type"], frame["data"])

        # 8. 收口恢复后的最终运行状态
        status = (
            RunFinalStatus.PAUSED
            if any(e.type == "approval_required" for e in events)
            else RunFinalStatus.COMPLETED
        )

        finalize_run_execution(
            db=db,
            run_id=approval.run_id,
            session_id=approval.session_id,
            user_input=run_input.user_input,
            status=status,
            events=events,
            reply=reply_text,
            effective_agent_name=agent_name,
            loop_state=agent_runner.state,
            last_usage=getattr(agent_runner, "last_usage", None),
            is_resume=True,
            recorder=rec,
        )

        if status == RunFinalStatus.PAUSED:
            next_pending = store_approval.get_next_pending_for_batch(
                batch_id=batch_id,
            )
            yield _sse_frame(
                "paused",
                {
                    "run_id": approval.run_id,
                    "approval_id": next_pending.id if next_pending else None,
                },
            )
        else:
            yield _sse_frame("end", {"state": agent_runner.state.model_dump()})

    except (GeneratorExit, asyncio.CancelledError):
        # Client interrupted after resume stream restarted
        finalize_run_execution(
            db=db,
            run_id=approval.run_id,
            session_id=approval.session_id,
            user_input=run_input.user_input,
            status=RunFinalStatus.CANCELLED,
            events=events,
            reply=reply_text,
            effective_agent_name=agent_name,
            loop_state=agent_runner.state,
            last_usage=getattr(agent_runner, "last_usage", None),
            is_resume=True,
            recorder=rec,
        )
        raise
    except Exception:
        # Runtime failed after resume stream restarted
        finalize_run_execution(
            db=db,
            run_id=approval.run_id,
            session_id=approval.session_id,
            user_input=run_input.user_input,
            status=RunFinalStatus.FAILED,
            events=events,
            reply=reply_text,
            effective_agent_name=agent_name,
            loop_state=agent_runner.state,
            last_usage=getattr(agent_runner, "last_usage", None),
            is_resume=True,
            recorder=rec,
        )
        raise
