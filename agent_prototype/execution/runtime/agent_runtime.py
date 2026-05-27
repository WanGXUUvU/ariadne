"""Agent 执行器。

职责：给定 AgentInput，驱动 LLM + 工具循环，产出 events 与最终 reply。
不负责数据库持久化，持久化由 service 层处理。
"""

# ── 标准库 ────────────────────────────────────────────────────────────────────
from typing import AsyncIterator, Iterator, Optional, Union

# ── 本地模块 ──────────────────────────────────────────────────────────────────
from agent_prototype.agent.definition import AgentDefinition, DEFAULT_AGENT_DEFINITION
from agent_prototype.api.dto.schemas import (
    AgentEvent, AgentInput, AgentOutput, AgentState,
    ApprovalPolicy, ChatMessage, RunMetadata,
    ToolCall, ToolCallFunction,
)
from agent_prototype.model.adapters.protocol import ModelAdapter
from agent_prototype.model.types.model_types import ModelStreamEvent
from agent_prototype.tools.registry import DEFAULT_TOOL_REGISTRY, ToolRegistry
from agent_prototype.execution.runtime.message_builder import build_model_request
from agent_prototype.execution.runtime.response_handler import build_final_turn
from agent_prototype.execution.runtime.tool_runner import (
    handle_tool_calls, async_handle_tool_calls,
)


# ── AgentRunner ───────────────────────────────────────────────────────────────

class AgentRunner:

    def __init__(
        self,
        state: Optional[AgentState] = None,
        definition: Optional[AgentDefinition] = None,
        tool_registry: Optional[ToolRegistry] = None,
        allow_tool_names: Optional[list[str]] = None,
        model_adapter: Optional[ModelAdapter] = None,
        approval_policy: ApprovalPolicy = ApprovalPolicy.NEVER,
        session_type:str="coding",
    ):
        self.state            = state or AgentState()
        self.definition       = definition or DEFAULT_AGENT_DEFINITION
        self.tool_registry    = tool_registry or DEFAULT_TOOL_REGISTRY
        self.allow_tool_names = (
            allow_tool_names if allow_tool_names is not None
            else self.definition.tool_names
        )
        self.model_adapter  = model_adapter
        self.approval_policy = approval_policy
        self.last_usage      = None
        self.session_type    =session_type

    # ── 非流式（保留备用） ────────────────────────────────────────────────────

    def run(self, agent_input: AgentInput) -> AgentOutput:
        """同步非流式运行一次，返回完整 AgentOutput。"""
        events: list[AgentEvent] = []
        event_index = 0

        self.state.messages.append(ChatMessage(role="user", content=agent_input.user_input))
        self.state.step += 1

        while True:
            request = build_model_request(
                self.definition, self.state,
                self.tool_registry, self.allow_tool_names,
                agent_input.session_id,
            )
            response = self.model_adapter.generate(request)
            assistant_message = response.assistant_message
            tool_calls = assistant_message.tool_calls or []

            if tool_calls:
                self.state.messages.append(assistant_message)
                tool_turn = handle_tool_calls(
                    self.tool_registry, tool_calls,
                    self.allow_tool_names, event_index,
                )
                events.extend(tool_turn.events)
                event_index = tool_turn.next_event_index
                for tool_message in tool_turn.tool_messages:
                    self.state.messages.append(tool_message)
                continue

            raw_reply = response.content or ""
            reply, final_event, assistant_message = build_final_turn(raw_reply, event_index)
            events.append(final_event)
            self.state.messages.append(assistant_message)

            return AgentOutput(
                reply=reply,
                state=self.state,
                events=events,
                usage=response.usage,
                metadata=RunMetadata(session_id=agent_input.session_id),
            )

    # ── 同步流式 ──────────────────────────────────────────────────────────────

    def stream_run(self, agent_input: AgentInput) -> Iterator[Union[AgentEvent, str]]:
        """同步 SSE 流式运行，逐步 yield AgentEvent 或 str(delta)。"""
        event_index = 0
        self.state.messages.append(ChatMessage(role="user", content=agent_input.user_input))
        self.state.step += 1

        while True:
            request = build_model_request(
                self.definition, self.state,
                self.tool_registry, self.allow_tool_names,
                agent_input.session_id,
            )

            raw_reply_chunks: list[str] = []
            tool_call_buffers: dict[int, dict] = {}
            finish_reason: Optional[str] = None

            for event in self.model_adapter.stream_generate(request):
                if event.type == "done" and event.usage:
                    self.last_usage = event.usage
                    continue
                if event.type == "thinking_delta":
                    yield event
                    continue

                finish_reason = event.finish_reason or finish_reason

                if event.content_delta:
                    yield event.content_delta
                    raw_reply_chunks.append(event.content_delta)

                if event.type == "tool_call_delta" and event.raw_event:
                    for tc in event.raw_event.get("tool_calls", [{}]):
                        idx = tc.get("index", 0)
                        if idx not in tool_call_buffers:
                            tool_call_buffers[idx] = {"id": "", "name_chunks": [], "args_chunks": []}
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
                self.state.messages.append(ChatMessage(role="assistant", tool_calls=tool_calls))
                tool_turn = handle_tool_calls(
                    self.tool_registry, tool_calls,
                    self.allow_tool_names, event_index,
                )
                for event in tool_turn.events:
                    yield event
                event_index = tool_turn.next_event_index
                for tool_message in tool_turn.tool_messages:
                    self.state.messages.append(tool_message)
                continue

            raw_reply = "".join(raw_reply_chunks)
            _, final_event, assistant_message = build_final_turn(raw_reply, event_index)
            yield final_event
            self.state.messages.append(assistant_message)
            break

    # ── 异步流式 ──────────────────────────────────────────────────────────────

    async def async_stream_run(
        self,
        agent_input: AgentInput,
        on_tool_start=None,
        on_tool_finish=None,
        on_approval_required=None,
        skip_user_message: bool = False,
        event_index: int = 0,
        run_id: Optional[str] = None,
        workspace_path: Optional[str] = None,
    ) -> AsyncIterator[Union[AgentEvent, str]]:
        """异步 SSE 流式运行，支持工具审批中断与恢复。"""
        if not skip_user_message:
            self.state.messages.append(ChatMessage(role="user", content=agent_input.user_input))
        self.state.step += 1

        while True:
            request = build_model_request(
                self.definition, self.state,
                self.tool_registry, self.allow_tool_names,
                agent_input.session_id,
            )

            raw_reply_chunks: list[str] = []
            tool_call_buffers: dict[int, dict] = {}
            finish_reason: Optional[str] = None

            async for event in self.model_adapter.async_stream_generate(request):
                if event.type == "done" and event.usage:
                    self.last_usage = event.usage
                    continue
                if event.type == "thinking_delta":
                    yield event
                    continue

                finish_reason = event.finish_reason or finish_reason

                if event.content_delta:
                    yield event.content_delta
                    raw_reply_chunks.append(event.content_delta)

                if event.type == "tool_call_delta" and event.raw_event:
                    for tc in event.raw_event.get("tool_calls", [{}]):
                        idx = tc.get("index", 0)
                        if idx not in tool_call_buffers:
                            tool_call_buffers[idx] = {"id": "", "name_chunks": [], "args_chunks": []}
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
                self.state.messages.append(ChatMessage(role="assistant", tool_calls=tool_calls))

                tool_turn = None
                async for item in async_handle_tool_calls(
                    self.tool_registry,
                    tool_calls,
                    self.allow_tool_names,
                    event_index,
                    session_id=agent_input.session_id,
                    on_tool_start=on_tool_start,
                    on_tool_finish=on_tool_finish,
                    approval_policy=self.approval_policy,
                    on_approval_required=on_approval_required,
                    saved_messages=list(self.state.messages),
                    run_id=run_id,
                    workspace_path=workspace_path,
                    session_type=getattr(self, "session_type", "coding"),
                ):
                    if isinstance(item, AgentEvent):
                        yield item
                    else:
                        tool_turn = item

                if tool_turn.paused_for_approval:
                    break
                if tool_turn.next_event_index is None:
                    raise RuntimeError("tool turn missing result")
                event_index = tool_turn.next_event_index
                for tool_message in tool_turn.tool_messages:
                    self.state.messages.append(tool_message)
                continue

            raw_reply = "".join(raw_reply_chunks)
            _, final_event, assistant_message = build_final_turn(raw_reply, event_index)
            yield final_event
            self.state.messages.append(assistant_message)
            break
