"""Agent 执行器。

职责：给定 RunInput，驱动 LLM + 工具循环，产出 events 与最终 reply。
不负责数据库持久化，持久化由 service 层处理。
"""

# ── 标准库 ────────────────────────────────────────────────────────────────────
from typing import AsyncIterator, Optional, Union

# ── 本地模块 ──────────────────────────────────────────────────────────────────
from agent_prototype.agent.types import AgentDefinition, DEFAULT_AGENT_DEFINITION
from agent_prototype.core.types import (
    ChatMessage,
    StreamChunk,
    ToolCall,
    ToolCallFunction,
    ModelAdapter,
)
from agent_prototype.execution.persistence.types import RunInput, RunOutput, RunMetadata
from agent_prototype.execution.runtime.types import RunEvent, RunState
from agent_prototype.security.policy.types import ApprovalPolicy
from agent_prototype.tools.registry import DEFAULT_TOOL_REGISTRY, ToolRegistry
from agent_prototype.execution.runtime.message_builder import build_model_request
from agent_prototype.execution.runtime.response_handler import build_reply
from agent_prototype.execution.runtime.tool_runner import (
    handle_tool_calls,
    async_handle_tool_calls,
)


# ── AgentRunner ───────────────────────────────────────────────────────────────


class AgentRunner:
    """这是一个“智能体运行载体（发动机）”。
    它的核心工作是驱动智能体与大模型之间的多轮对话循环。
    它接收用户的输入，整理当前的聊天历史，把请求发给大模型；
    如果大模型说“我要调用工具”，它就会通过工具注册中心（ToolRegistry）去执行工具，再把执行结果反馈给大模型，直到大模型最终给出一个人类可读的文字回答。
    """

    def __init__(
        self,
        state: Optional[RunState] = None,
        agent_profile: Optional[AgentDefinition] = None,
        tool_registry: Optional[ToolRegistry] = None,
        model_adapter: Optional[ModelAdapter] = None,
        approval_policy: ApprovalPolicy = ApprovalPolicy.NEVER,
        session_type: str = "coding",
    ):
        """组装这个智能体发动机，给他配置好初始聊天状态、人设定义、可用的工具箱、大模型电话线、审批策略等参数。

        需要拿到的东西：
        - state: 智能体当前的聊天状态，比如历史聊天记录（不传就默认新建一个空状态）。
        - definition: 智能体的人设定义（比如系统提示词是什么）。
        - tool_registry: 工具注册中心（工具箱）。
        - allow_tool_names: 这次运行允许调用的工具名字清单（不传就用人设定义里的）。
        - model_adapter: 大模型适配器（大模型电话线）。
        - approval_policy: 审批策略，决定调用工具时需不需要人类手动审批（默认从不审批）。
        - session_type: 会话类型（默认是写代码模式 "coding"）。
        """
        self.state = state or RunState()
        self.agent_profile = agent_profile or DEFAULT_AGENT_DEFINITION
        self.tool_registry = tool_registry or DEFAULT_TOOL_REGISTRY
        self.model_adapter = model_adapter
        self.approval_policy = approval_policy
        self.last_usage = None
        self.session_type = session_type

    # ── 非流式（保留备用） ────────────────────────────────────────────────────

    def execute(self, run_input: RunInput, run_id: Optional[str] = None) -> RunOutput:
        """同步普通运行模式：让发动机一口气轰鸣运转到结束！
        把用户输入塞进历史，然后在大模型和工具调用之间来回循环，直到大模型给出最终文字回答，最后把整个运行包成一个 RunOutput 吐出来。
        这个方法是“同步阻塞”的，会一直等完全部过程。

        需要拿到的东西：
        - run_input: 用户的本轮输入参数对象。

        会给出来的结果：
        - 一个完整的 RunOutput 运行结果对象，包含最终文本回答、所有产生过的事件、最新的状态等。
        """
        events: list[RunEvent] = []
        event_index = 0

        self.state.messages.append(ChatMessage(role="user", content=run_input.user_input))
        self.state.step += 1

        while True:
            request = build_model_request(
                self.agent_profile,
                self.state,
                self.tool_registry,
            )
            response = self.model_adapter.generate(request)
            assistant_message = response.assistant_message
            tool_calls = assistant_message.tool_calls or []

            if tool_calls:
                leadin = assistant_message.content or ""
                if leadin.strip():
                    events.append(
                        RunEvent(
                            index=event_index,
                            type="assistant_text",
                            content=leadin,
                        )
                    )
                    event_index += 1
                self.state.messages.append(assistant_message)
                tool_batch = handle_tool_calls(
                    self.tool_registry,
                    tool_calls,
                    self.agent_profile.tool_names,
                    event_index,
                    session_id=run_input.session_id,
                    run_id=run_id,
                    workspace_path=getattr(run_input, "workspace_path", None),
                )
                events.extend(tool_batch.events)
                event_index = tool_batch.next_event_index
                for tool_message in tool_batch.tool_messages:
                    self.state.messages.append(tool_message)
                continue

            raw_reply = response.content or ""
            reply, final_event, assistant_message = build_reply(raw_reply, event_index)
            events.append(final_event)
            self.state.messages.append(assistant_message)

            return RunOutput(
                reply=reply,
                state=self.state,
                events=events,
                usage=response.usage,
                metadata=RunMetadata(session_id=run_input.session_id),
            )

    # ── 异步流式 ──────────────────────────────────────────────────────────────

    async def async_stream_run(
        self,
        run_input: RunInput,
        on_tool_start=None,
        on_tool_finish=None,
        on_approval_required=None,
        skip_user_message: bool = False,
        event_index: int = 0,
        run_id: Optional[str] = None,
        workspace_path: Optional[str] = None,
    ) -> AsyncIterator[Union[RunEvent, str, StreamChunk]]:
        """异步流式运行模式（最强大的模式！）：支持异步并发、支持工具调用的审批中断、并且能将思考过程和执行步骤实时吐出。
        在这个模式下，如果大模型调用的工具需要人工审批，它会及时暂停，保留现场并 yield 审批事件，等待人类介入审批通过后，再由 Resume 恢复运行。

        需要拿到的东西：
        - run_input: 用户的本轮输入参数。
        - on_tool_start: 当工具开始执行时的回调函数（可选）。
        - on_tool_finish: 当工具执行结束时的回调函数（可选）。
        - on_approval_required: 当需要审批时的回调函数（可选）。
        - skip_user_message: 是否跳过自动往历史里塞用户消息（如果前面已经塞过了，这里传 True）。
        - event_index: 序列号起始索引（默认为 0）。
        - run_id: 这次运行的 ID（可选）。
        - workspace_path: 工作区物理路径（可选）。

        会给出来的结果：
        - 一个异步迭代器，实时产生大模型吐出的字片段（str）或者执行中产生的关键事件（RunEvent）。
        """
        if not skip_user_message:
            last_user = None
            for msg in reversed(self.state.messages):
                if msg.role == "user":
                    last_user = msg
                    break
            if not (last_user and last_user.content == run_input.user_input):
                self.state.messages.append(ChatMessage(role="user", content=run_input.user_input))
        self.state.step += 1

        while True:
            request = build_model_request(
                self.agent_profile,
                self.state,
                self.tool_registry,
            )

            raw_reply_chunks: list[str] = []
            tool_call_buffers: dict[int, dict] = {}
            finish_reason: Optional[str] = None

            async for chunk in self.model_adapter.async_stream_generate(request):
                if chunk.finish_reason:
                    finish_reason = chunk.finish_reason
                if chunk.type == "done" and chunk.usage:
                    self.last_usage = chunk.usage
                    continue
                if chunk.type == "thinking_delta":
                    yield chunk
                    continue
                if chunk.type == "content_delta" and chunk.content_delta:
                    yield chunk.content_delta
                    raw_reply_chunks.append(chunk.content_delta)
                if chunk.type == "tool_call_delta" and chunk.tool_call_delta:
                    for tc in chunk.tool_call_delta.get("tool_calls", [{}]):
                        idx = tc.get("index", 0)
                        if idx not in tool_call_buffers:
                            tool_call_buffers[idx] = {
                                "id": "",
                                "name_chunks": [],
                                "args_chunks": [],
                            }
                        buf = tool_call_buffers[idx]
                        buf["id"] = buf["id"] or tc.get("id", "")
                        fn = tc.get("function", {})
                        buf["name_chunks"].append(fn.get("name", ""))
                        buf["args_chunks"].append(fn.get("arguments", ""))

            if finish_reason == "tool_calls":
                tool_calls = [
                    ToolCall(
                        id=buf["id"],
                        function=ToolCallFunction(
                            name="".join(buf["name_chunks"]),
                            arguments="".join(buf["args_chunks"]),
                        ),
                    )
                    for buf in tool_call_buffers.values()
                ]
                raw_leadin = "".join(raw_reply_chunks)
                if raw_leadin.strip():
                    yield RunEvent(
                        index=event_index,
                        type="assistant_text",
                        content=raw_leadin,
                    )
                    event_index+=1
                self.state.messages.append(ChatMessage(
                    role="assistant",
                    content=raw_leadin if raw_leadin.strip() else None,
                    tool_calls=tool_calls,
                ))

                tool_batch_result = None
                async for item in async_handle_tool_calls(
                    self.tool_registry,
                    tool_calls,
                    self.agent_profile.tool_names,
                    event_index,
                    session_id=run_input.session_id,
                    on_tool_start=on_tool_start,
                    on_tool_finish=on_tool_finish,
                    approval_policy=self.approval_policy,
                    on_approval_required=on_approval_required,
                    saved_messages=list(self.state.messages),
                    run_id=run_id,
                    workspace_path=workspace_path,
                    session_type=getattr(self, "session_type", "coding"),
                ):
                    if isinstance(item, RunEvent):
                        yield item
                    else:
                        tool_batch_result = item
                for tool_message in tool_batch_result.tool_messages:
                    self.state.messages.append(tool_message)
                if tool_batch_result.paused_for_approval:
                    break
                if tool_batch_result.next_event_index is None:
                    raise RuntimeError("tool turn missing result")
                event_index = tool_batch_result.next_event_index
                continue
            if finish_reason=="stop":
                raw_reply = "".join(raw_reply_chunks)
                _, final_event, assistant_message = build_reply(raw_reply, event_index)
                yield final_event
                self.state.messages.append(assistant_message)
                break
