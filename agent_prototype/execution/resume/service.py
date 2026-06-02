"""审批恢复运行编排层。

职责：
- 根据 approval_id 重建 Agent 上下文（恢复消息 + 加载定义 + 构建 Adapter）
- 执行审批结果（通过 / 拒绝），拼装工具结果事件
- 拉起 Agent 继续流式运转，yield SSE 帧
- 运行结束后委托 RunPersistenceService 落库

不负责：感知 HTTP 协议、直接操作 DB 模型。
上游：approval_routes.py
下游：RuntimeContextFactory.build_adapter / RunPersistenceService.save_resumed
"""

# ── 标准库 ────────────────────────────────────────────────────────────────────
import asyncio
from typing import AsyncIterator

# ── 第三方库 ──────────────────────────────────────────────────────────────────
from sqlalchemy.orm import Session

# ── 本地模块 ──────────────────────────────────────────────────────────────────
from agent_prototype.execution.persistence.types import AgentInput
from agent_prototype.execution.runtime.types import AgentEvent, AgentState
from agent_prototype.tools.result_types import ToolResult
from agent_prototype.core.types import ChatMessage
from agent_prototype.execution.streaming.types import StreamFrame
from agent_prototype.memory.session.store import SqliteSessionStore
from agent_prototype.infra.db.orm_models import SessionRunRecord
from agent_prototype.security.approval.store import SqliteApprovalStore
from agent_prototype.security.middleware.base import MiddlewarePipeline, ToolCallContext
from agent_prototype.security.sandbox.middleware import SandboxMiddleware
from agent_prototype.tools.registry import build_run_registry
from agent_prototype.execution.runtime.agent_runtime import AgentRunner
from agent_prototype.execution.streaming.sse import _sse_frame
from agent_prototype.agent.definition import AgentDefinitionService
from agent_prototype.execution.persistence.service import RunPersistenceService
from agent_prototype.execution.runtime_context_factory import RuntimeContextFactory


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
        self.persist = RunPersistenceService(db)
        self.session_store = SqliteSessionStore(db)

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
        state = AgentState(messages=messages)
        batch_id = approval.batch_id or approval.run_id

        # ── 加载 Agent 定义 ───────────────────────────────────────────────────
        run_record = (
            self.db.query(SessionRunRecord)
            .filter(SessionRunRecord.run_id == approval.run_id)
            .first()
        )
        agent_name = run_record.agent_name if run_record else "default"
        definition = AgentDefinitionService(self.db).load_definition(agent_name)

        # ── 构建 tool registry & adapter ─────────────────────────────────────
        tool_registry = build_run_registry(
            child_dispatcher=lambda task, agent_name="子Agent": None,
            status_checker=lambda ids: {},
            child_waiter=lambda run_id: "",
        )
        model_adapter = RuntimeContextFactory(self.db).build_adapter(approval.session_id)

        # ── 执行审批结果，构造工具结果事件 ────────────────────────────────────
        event_index = approval.event_index
        if rejected:
            content = "[TOOL_REJECTED] 用户拒绝了此工具调用"
            tr = ToolResult(ok=False, content=content)
        else:
            loop = asyncio.get_event_loop()
            workspace_path = self.session_store.read_session_record(
                approval.session_id
            ).workspace_path
            pipeline = MiddlewarePipeline([SandboxMiddleware()])

            progress_queue: asyncio.Queue[AgentEvent] = asyncio.Queue()

            async def on_progress(text: str) -> None:
                await progress_queue.put(
                    AgentEvent(
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
                extra={
                    "workspace_path": workspace_path,
                    "allow_tool_names": definition.tool_names,
                },
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
                        StreamFrame(type="agent_event", data=progress_event.model_dump())
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

        tool_result_event = AgentEvent(
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
        yield _sse_frame(StreamFrame(type="agent_event", data=tool_result_event.model_dump()))

        # ── 关键：刷新剩余 pending approvals 的 saved_messages ──────────────
        self.approval_store.refresh_pending_saved_messages_for_batch(
            batch_id=batch_id,
            saved_messages=state.messages,
            event_index=event_index,
        )

        # ── 关键：如果同 run 还有别的 pending approval，先别继续模型 ───────
        if not self.approval_store.is_batch_fully_resolved(batch_id):
            next_pending = self.approval_store.get_next_pending_for_batch(batch_id)
            self.persist.save_resumed_partial(
                run_id=approval.run_id,
                session_id=approval.session_id,
                events=[tool_result_event],
                agent_state=state,
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

        yield _sse_frame(
            StreamFrame(
                type="end",
                data={
                    "reply": partial_reply,
                    "run_id": approval.run_id,
                    "state": agent.state.model_dump(),
                },
            )
        )
