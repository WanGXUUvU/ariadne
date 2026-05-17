"""Agent 执行器。

这个文件只负责“一次 run 怎么跑”：
- 把用户输入追加进上下文
- 调用 LLM
- 处理 tool calls
- 生成结构化 events
- 返回最终 reply 和最新 state

它不负责数据库持久化；持久化由 service 层处理。
"""

from typing import Iterator, Optional, Union,AsyncIterator

from ..core.agent_definition import AgentDefinition, DEFAULT_AGENT_DEFINITION
from ..core.schemas import AgentEvent, AgentInput, AgentOutput, AgentState, ChatMessage, RunMetadata,ToolCall, ToolCallFunction
from ..model.adapter import ModelAdapter
from ..tools.tool_registry import DEFAULT_TOOL_REGISTRY, ToolRegistry
from .message_builder import build_model_request
from .response_handler import build_final_turn
from .tool_executor import handle_tool_calls,async_handle_tool_calls

class Agent:

    def __init__(
        self,
        state: Optional[AgentState] = None,
        definition: Optional[AgentDefinition] = None,
        tool_registry: Optional[ToolRegistry] = None,
        allow_tool_names: Optional[list[str]] = None,
        model_adapter:Optional[ModelAdapter]=None,
    ):
        """输入：可选 state、agent 定义、工具注册表、允许工具名列表。输出：初始化后的 Agent 实例。"""
        self.state = state or AgentState()
        self.definition = definition or DEFAULT_AGENT_DEFINITION
        self.tool_registry = tool_registry or DEFAULT_TOOL_REGISTRY
        self.allow_tool_names = allow_tool_names if allow_tool_names is not None else self.definition.tool_names
        self.model_adapter = model_adapter

    def run(self, agent_input: AgentInput) -> AgentOutput:
        """输入：AgentInput 请求对象。输出：包含 reply、state、events 的 AgentOutput。"""

        events: list[AgentEvent] = []
        event_index = 0

        self.state.messages.append(ChatMessage(role="user", content=agent_input.user_input))
        self.state.step += 1

        while True:
            request = build_model_request(
                self.definition,
                self.state,
                self.tool_registry,
                self.allow_tool_names,
                agent_input.session_id,
            )
            response = self.model_adapter.generate(request)
            assistant_message = response.assistant_message
            tool_calls = assistant_message.tool_calls or []

            if tool_calls:
                self.state.messages.append(assistant_message)

                tool_turn = handle_tool_calls(
                    self.tool_registry,
                    tool_calls,
                    self.allow_tool_names,
                    event_index,
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
                metadata=RunMetadata(
                    session_id=agent_input.session_id,
                ),
            )
    
    def stream_run(self, agent_input: AgentInput) -> Iterator[Union[AgentEvent, str]]:
        """输入：AgentInput。输出：逐步 yield AgentEvent（工具阶段）或 str（delta，最终回答阶段）。"""

        event_index = 0
        self.state.messages.append(ChatMessage(role="user", content=agent_input.user_input))
        self.state.step += 1

        while True:
            request = build_model_request(
                self.definition,
                self.state,
                self.tool_registry,
                self.allow_tool_names,
                agent_input.session_id,
            )
            # 改成（一次调用）
            raw_reply_chunks: list[str] = []
            tool_call_buffers: dict[int, dict] = {}
            # 结构：{ 0: {"id": "call_001", "name_chunks": [], "args_chunks": []},
            #        1: {"id": "call_002", "name_chunks": [], "args_chunks": []} }
            finish_reason: Optional[str]=None

            for event in self.model_adapter.stream_generate(request):
                finish_reason = event.finish_reason or finish_reason

                if event.content_delta:
                    yield event.content_delta          # 文字 → 推给前端
                    raw_reply_chunks.append(event.content_delta)

                if event.type == "tool_call_delta" and event.raw_event:
                    for tc in event.raw_event.get("tool_calls", [{}]):
                        idx=tc.get("index",0)
                        if idx not in tool_call_buffers:
                            tool_call_buffers[idx]= {"id": "", "name_chunks": [], "args_chunks": []}
                        buf = tool_call_buffers[idx]
                        buf["id"] = buf["id"] or tc.get("id", "")
                        fn = tc.get("function", {})
                        buf["name_chunks"].append(fn.get("name", ""))
                        buf["args_chunks"].append(fn.get("arguments", ""))

            if finish_reason == "tool_calls":
                # 拼成完整 tool call，交给工具执行
                tool_calls = [
                    ToolCall(
                        id=buf["id"],
                        function=ToolCallFunction(
                            name="".join(buf["name_chunks"]),
                            arguments="".join(buf["args_chunks"]),
                        )
                    )
                    for buf in tool_call_buffers.values()
                ]
                # 把 assistant message 追加进 state（只有 tool_calls，没有 content）
                self.state.messages.append(ChatMessage(
                    role="assistant",
                    tool_calls=tool_calls,
                ))
                tool_turn = handle_tool_calls(
                    self.tool_registry,
                    tool_calls,
                    self.allow_tool_names,
                    event_index,
                )
                for event in tool_turn.events:
                    yield event
                event_index = tool_turn.next_event_index
                for tool_message in tool_turn.tool_messages:
                    self.state.messages.append(tool_message)
                continue   # 继续下一轮

            # finish_reason == "stop"，正常结束
            raw_reply = "".join(raw_reply_chunks)
            _, final_event, assistant_message = build_final_turn(raw_reply, event_index)
            yield final_event
            self.state.messages.append(assistant_message)
            break

    async def async_stream_run(self, agent_input: AgentInput,on_tool_start=None,on_tool_finish=None,) -> AsyncIterator[Union[AgentEvent, str]]:
        """输入：AgentInput。输出：逐步 yield AgentEvent（工具阶段）或 str（delta，最终回答阶段）。"""

        event_index = 0
        self.state.messages.append(ChatMessage(role="user", content=agent_input.user_input))
        self.state.step += 1

        while True:
            request = build_model_request(
                self.definition,
                self.state,
                self.tool_registry,
                self.allow_tool_names,
                agent_input.session_id,
            )
            # 改成（一次调用）
            raw_reply_chunks: list[str] = []
            tool_call_buffers: dict[int, dict] = {}
            # 结构：{ 0: {"id": "call_001", "name_chunks": [], "args_chunks": []},
            #        1: {"id": "call_002", "name_chunks": [], "args_chunks": []} }
            finish_reason: Optional[str]=None

            async for event in self.model_adapter.async_stream_generate(request):
                finish_reason = event.finish_reason or finish_reason

                if event.content_delta:
                    yield event.content_delta          # 文字 → 推给前端
                    raw_reply_chunks.append(event.content_delta)

                if event.type == "tool_call_delta" and event.raw_event:
                    for tc in event.raw_event.get("tool_calls", [{}]):
                        idx=tc.get("index",0)
                        if idx not in tool_call_buffers:
                            tool_call_buffers[idx]= {"id": "", "name_chunks": [], "args_chunks": []}
                        buf = tool_call_buffers[idx]
                        buf["id"] = buf["id"] or tc.get("id", "")
                        fn = tc.get("function", {})
                        buf["name_chunks"].append(fn.get("name", ""))
                        buf["args_chunks"].append(fn.get("arguments", ""))

            if finish_reason == "tool_calls":
                # 拼成完整 tool call，交给工具执行
                tool_calls = [
                    ToolCall(
                        id=buf["id"],
                        function=ToolCallFunction(
                            name="".join(buf["name_chunks"]),
                            arguments="".join(buf["args_chunks"]),
                        )
                    )
                    for buf in tool_call_buffers.values()
                ]
                # 把 assistant message 追加进 state（只有 tool_calls，没有 content）
                self.state.messages.append(ChatMessage(
                    role="assistant",
                    tool_calls=tool_calls,
                ))
                tool_turn = await async_handle_tool_calls(
                    self.tool_registry,
                    tool_calls,
                    self.allow_tool_names,
                    event_index,
                    on_tool_start=on_tool_start,
                    on_tool_finish=on_tool_finish,
                )
                for event in tool_turn.events:
                    yield event
                event_index = tool_turn.next_event_index
                for tool_message in tool_turn.tool_messages:
                    self.state.messages.append(tool_message)
                continue   # 继续下一轮

            # finish_reason == "stop"，正常结束
            raw_reply = "".join(raw_reply_chunks)
            _, final_event, assistant_message = build_final_turn(raw_reply, event_index)
            yield final_event
            self.state.messages.append(assistant_message)
            break