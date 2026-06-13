"""审批恢复运行编排层。

职责：
- 根据 approval_id 重建 Agent 上下文（恢复消息 + 加载定义 + 构建 Adapter）
- 执行审批结果（通过 / 拒绝），拼装工具结果事件
- 拉起 Agent 继续流式运转，yield SSE 帧
- 运行结束后委托 RunRecorder 落库

不负责：感知 HTTP 协议、直接操作 DB 模型。
上游：approval_routes.py
下游：RunContextFactory.create_adapter / RunRecorder.finalize_run
"""

# ── 标准库 ────────────────────────────────────────────────────────────────────
import asyncio
from typing import AsyncIterator

# ── 第三方库 ──────────────────────────────────────────────────────────────────
from sqlalchemy.orm import Session

# ── 本地模块 ──────────────────────────────────────────────────────────────────
from agent_prototype.execution.persistence.types import (
    RunInput,
    RunFinalizationInput,
    RunFinalStatus,
    RunContext,
)
from agent_prototype.execution.runtime.types import RunEvent, RunState
from agent_prototype.tools.result_types import ToolResult
from agent_prototype.core.types import ChatMessage
from agent_prototype.execution.streaming.types import StreamFrame
from agent_prototype.memory.session.store import SessionStore
from agent_prototype.memory.run.store import RunTraceStore
from agent_prototype.infra.db.orm_models import SessionRunRecord
from agent_prototype.security.approval.store import SqliteApprovalStore
from agent_prototype.security.middleware.base import MiddlewarePipeline, ToolCallContext
from agent_prototype.security.sandbox.middleware import SandboxMiddleware
from agent_prototype.tools.registry import build_run_registry
from agent_prototype.execution.runtime.agent_runner import AgentRunner
from agent_prototype.execution.runtime.run_lifecycle import (
    RunEventItem,
    RunStatusItem,
    RunLifecycleParams,
    RunLifecycle,
    TextDeltaItem,
    ThinkingDeltaItem,
)
from agent_prototype.execution.streaming.sse import _sse_frame
from agent_prototype.agent.definition import AgentDefinitionService
from agent_prototype.execution.persistence.run_recorder import RunRecorder
from agent_prototype.execution.run_context_factory import RunContextFactory
from agent_prototype.execution.runtime.vfs import RunVfsRegistry
from agent_prototype.observation.tool_tracer import ToolTracer


class ResumeRunService:
    """这是一个“审批通过后的恢复运行指挥官”。
    它的核心职责是：当一个需要敏感权限的工具调用被人工审批（通过或拒绝）之后，
    重建这个智能体中断时的上下文环境（还原聊天历史、接通大模型适配器），
    把审批后的工具执行结果塞给智能体，然后拉起智能体继续顺着之前中断的地方流式往下运行，并将结果保存落库。
    """

    def __init__(self, db: Session):
        """初始化恢复运行指挥官，给他分配数据库连接、审批仓库、落库助手和会话仓库。

        需要拿到的东西：
        - db: 数据库连接会话对象。
        """
        self.db = db
        self.approval_store = SqliteApprovalStore(db)
        self.persist = RunRecorder(db)
        self.session_store = SessionStore(db)

    async def resume_run(self, approval_id: str, rejected: bool = False) -> AsyncIterator[str]:
        """执行审批结果并拉起智能体继续运行！
        它会先去读审批记录，把之前的聊天历史原样倒回智能体内存，
        如果用户“同意”就真正去执行那个敏感工具，拿回工具执行结果；如果用户“拒绝”就构造一个被拒绝的失败结果。
        接着，它会把这个结果以 `tool_result` 事件吐给前端，并重新建立 AgentRunner，让智能体顺着这个结果继续流式推导、回答，
        最后在运行结束时把所有追回来的数据和状态一并落库。

        需要拿到的东西：
        - approval_id: 之前等待审批的那条记录的唯一 ID。
        - rejected: 用户是选择拒绝（True）还是同意（False，默认）。

        会给出来的结果：
        - 一个异步迭代器，实时以 SSE 格式吐出恢复运行后的各种 StreamFrame 帧数据。
        """
        approval = self.approval_store.get(approval_id)
        messages = self.approval_store.restore_messages(approval)
        state = RunState(messages=messages)
        batch_id = approval.batch_id or approval.run_id

        # ── 加载 Agent 定义 ───────────────────────────────────────────────────
        run_record = (
            self.db.query(SessionRunRecord)
            .filter(SessionRunRecord.run_id == approval.run_id)
            .first()
        )
        agent_name = run_record.agent_name if run_record else "default"
        agent_profile = AgentDefinitionService(self.db).load_definition(agent_name)

        # ── 构建 tool registry & adapter ─────────────────────────────────────
        tool_registry = build_run_registry(
            child_dispatcher=lambda task, agent_name="子Agent": None,
            status_checker=lambda ids: {},
            child_waiter=lambda run_id: "",
        )
        runtime_factory = RunContextFactory(self.db)
        model_adapter = runtime_factory.create_adapter(approval.session_id)
        session_record = self.session_store.load_record(approval.session_id)
        approval_policy = runtime_factory._resolve_approval_policy(session_record)

        # ── 执行审批结果，构造工具结果事件 ────────────────────────────────────
        event_index = approval.event_index
        if rejected:
            content = "[TOOL_REJECTED] 用户拒绝了此工具调用"
            tr = ToolResult(ok=False, content=content)
        else:
            loop = asyncio.get_event_loop()
            workspace_path = session_record.workspace_path if session_record else None
            pipeline = MiddlewarePipeline([SandboxMiddleware()])
            extra = {
                "workspace_path": workspace_path,
                "allow_tool_names": agent_profile.tool_names,
            }
            vfs = RunVfsRegistry.get(approval.run_id)
            if vfs is not None:
                extra["vfs"] = vfs

            progress_queue: asyncio.Queue[RunEvent] = asyncio.Queue()

            async def on_progress(text: str) -> None:
                await progress_queue.put(
                    RunEvent(
                        index=0,  # 占位，真正序号由恢复链主循环统一赋值
                        type="tool_progress",
                        content=text,
                        tool_name=approval.tool_name,
                        tool_call_id=approval.tool_call_id,
                    )
                )

            context = ToolCallContext(
                tool_name=approval.tool_name,
                tool_args=approval.arguments,
                tool_call_id=approval.tool_call_id,
                session_id=approval.session_id,
                run_id=approval.run_id,
                extra=extra,
                on_progress=on_progress,
                loop=loop,
            )

            async def terminal_execute_call() -> ToolResult:
                return await loop.run_in_executor(
                    None,
                    tool_registry.execute_tool_call,
                    context.tool_name,
                    context.tool_args,
                    context,
                )

            execute_task = asyncio.create_task(pipeline.execute(context, terminal_execute_call))

            while True:
                if execute_task.done() and progress_queue.empty():
                    break

                queue_get_task = asyncio.create_task(progress_queue.get())
                done, pending = await asyncio.wait(
                    [execute_task, queue_get_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if queue_get_task in done:
                    progress_event = queue_get_task.result()
                    progress_event.index = event_index
                    event_index += 1
                    yield _sse_frame(
                        StreamFrame(type="run_event", data=progress_event.model_dump())
                    )
                else:
                    queue_get_task.cancel()

            tool_result = execute_task.result()
            content = (
                tool_result.content
                if tool_result.ok
                else f"[TOOL_ERROR] {tool_result.error.message}"
            )
            tr = ToolResult(ok=tool_result.ok, content=content)

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
            ChatMessage(role="tool", tool_call_id=approval.tool_call_id, content=content)
        )
        yield _sse_frame(StreamFrame(type="resume", data={"run_id": approval.run_id}))
        yield _sse_frame(StreamFrame(type="run_event", data=tool_result_event.model_dump()))

        # ── 关键：刷新剩余 pending approvals 的 saved_messages ──────────────
        self.approval_store.refresh_pending_saved_messages_for_batch(
            batch_id=batch_id,
            saved_messages=state.messages,
            event_index=event_index,
        )

        # ── 关键：如果同 run 还有别的 pending approval，先别继续模型 ───────
        if not self.approval_store.is_batch_fully_resolved(batch_id):
            next_pending = self.approval_store.get_next_pending_for_batch(batch_id)
            self.persist.finalize_run(
                RunFinalizationInput(
                    session_id=approval.session_id,
                    run_id=approval.run_id,
                    status=RunFinalStatus.PAUSED,
                    user_input="",
                    reply_text="",
                    agent_name=agent_name,
                    events=[tool_result_event],
                    state=state,
                    append_events=True,
                )
            )
            yield _sse_frame(
                StreamFrame(
                    type="paused",
                    data={
                        "run_id": approval.run_id,
                        "approval_id": next_pending.id if next_pending else None,
                    },
                )
            )
            return

        # ── 构造 AgentRunner，继续流式运转 ────────────────────────────────────
        agent_runner = AgentRunner(
            state=state,
            agent_profile=agent_profile,
            model_adapter=model_adapter,
            tool_registry=tool_registry,
            approval_policy=approval_policy,
        )
        run_input = RunInput.model_construct(
            session_id=approval.session_id,
            user_input="",
            agent_name=None,
            skill_name=None,
        )
        workspace_path = session_record.workspace_path if session_record else None
        ctx = RunContext(
            state=state,
            agent_profile=agent_profile,
            adapter=model_adapter,
            approval_policy=approval_policy,
            effective_agent_name=agent_name,
            workspace_path=workspace_path or "",
            session_type="coding",
        )
        observer = ToolTracer(
            self.db,
            RunTraceStore(self.db),
            self.approval_store,
            approval.session_id,
            approval.run_id,
            run_input,
        )
        lifecycle = RunLifecycle(
            RunLifecycleParams(
                ctx=ctx,
                agent_runner=agent_runner,
                persist=self.persist,
                run_input=run_input,
                run_id=approval.run_id,
                on_tool_start=observer.on_tool_start,
                on_tool_finish=observer.on_tool_finish,
                on_approval_required=observer.on_approval_required,
                skip_user_message=True,
                event_index=event_index,
                initial_events=[tool_result_event],
                append_events=True,
            )
        )

        async for item in lifecycle.iterate():
            if isinstance(item, TextDeltaItem):
                yield _sse_frame(StreamFrame(type="delta", data={"content": item.content}))
            elif isinstance(item, ThinkingDeltaItem):
                yield _sse_frame(
                    StreamFrame(type="thinking_delta", data={"content": item.content})
                )
            elif isinstance(item, RunEventItem):
                yield _sse_frame(
                    StreamFrame(type="run_event", data=item.event.model_dump())
                )
            elif isinstance(item, RunStatusItem):
                if item.status == RunFinalStatus.PAUSED:
                    next_pending = self.approval_store.get_next_pending_for_batch(batch_id)
                    yield _sse_frame(
                        StreamFrame(
                            type="paused",
                            data={
                                "run_id": approval.run_id,
                                "approval_id": next_pending.id if next_pending else None,
                            },
                        )
                    )
                else:
                    yield _sse_frame(
                        StreamFrame(
                            type="end",
                            data={
                                "run_id": approval.run_id,
                                "state": agent_runner.state.model_dump(),
                            },
                        )
                    )
