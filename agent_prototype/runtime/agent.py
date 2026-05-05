"""Agent 执行器。

这个文件只负责“一次 run 怎么跑”：
- 把用户输入追加进上下文
- 调用 LLM
- 处理 tool calls
- 生成结构化 events
- 返回最终 reply 和最新 state

它不负责数据库持久化；持久化由 service 层处理。
"""

from typing import Optional

from ..core.agent_definition import AgentDefinition, DEFAULT_AGENT_DEFINITION
from ..core.schemas import AgentEvent, AgentInput, AgentOutput, AgentState, ChatMessage, ToolCall,RunMetadata
from .llm_client import call_llm
from .tool_registry import DEFAULT_TOOL_REGISTRY, ToolRegistry


def strip_think(content: str) -> str:
    """输入：模型原始回复文本。输出：去掉 think 包裹后的用户可见文本。"""

    if "</think>" not in content:
        return content.strip()
    # `split(sep, 1)` 只切一次，保留 `</think>` 后面的正文。
    return content.split("</think>", 1)[1].strip()


class Agent:
    """单次 agent 执行器。

    这个类接收：
    - 当前 session state
    - agent 定义
    - 工具注册表

    然后完成一次完整的“模型 -> 工具 -> 模型”闭环。
    """

    def __init__(
        self,
        state: Optional[AgentState] = None,
        definition: Optional[AgentDefinition] = None,
        tool_registry: Optional[ToolRegistry] = None,
        allow_tool_names: Optional[list[str]] = None,
    ):
        """输入：可选 state、agent 定义、工具注册表、允许工具名列表。输出：初始化后的 Agent 实例。"""
        self.state = state or AgentState()
        self.definition = definition or DEFAULT_AGENT_DEFINITION
        self.tool_registry = tool_registry or DEFAULT_TOOL_REGISTRY
        self.allow_tool_names = allow_tool_names if allow_tool_names is not None else self.definition.tool_names

    def run(self, agent_input: AgentInput) -> AgentOutput:
        """输入：AgentInput 请求对象。输出：包含 reply、state、events 的 AgentOutput。"""

        events = []
        event_index = 0

        self.state.messages.append(ChatMessage(role="user", content=agent_input.user_input))
        self.state.step += 1

        # 发送给模型的消息 = system prompt + 历史消息 + 当前用户输入。
        messages = [ChatMessage(role="system", content=self.definition.system_prompt)] + self.state.messages

        while True:
            # 这里把 Pydantic 对象转成普通字典，方便交给 LLM client。
            assistant_msg = call_llm(
                [message.model_dump(exclude_none=True) for message in messages],
                self.tool_registry.get_tool_schemas(self.allow_tool_names),
            )

            if assistant_msg.get("tool_calls"):
                assistant_message = ChatMessage(
                    role="assistant",
                    content=assistant_msg.get("content"),
                    tool_calls=[ToolCall.model_validate(tool_call) for tool_call in assistant_msg["tool_calls"]],
                )
                messages.append(assistant_message)
                self.state.messages.append(assistant_message)

                for tool_call in assistant_message.tool_calls or []:
                    events.append(
                        AgentEvent(
                            index=event_index,
                            type="assistant_tool_call",
                            tool_name=tool_call.function.name,
                            tool_call_id=tool_call.id,
                            content=tool_call.function.arguments,
                        )
                    )
                    event_index += 1

                    if self.allow_tool_names is not None and tool_call.function.name not in self.allow_tool_names:
                        raise ValueError(f"Tool not allowed:{tool_call.function.name}")

                    tool_result = self.tool_registry.execute_tool_call(
                        tool_call.function.name,
                        tool_call.function.arguments,
                    )

                    if tool_result.ok:
                        events.append(
                            AgentEvent(
                                index=event_index,
                                type="tool_result",
                                tool_name=tool_call.function.name,
                                tool_call_id=tool_call.id,
                                content=tool_result.content,
                                tool_result=tool_result,
                            )
                        )
                        tool_message = ChatMessage(
                            role="tool",
                            tool_call_id=tool_call.id,
                            content=tool_result.content,
                        )
                    else:
                        error_message = tool_result.error.message if tool_result.error else "Tool failed"
                        events.append(
                            AgentEvent(
                                index=event_index,
                                type="tool_error",
                                tool_name=tool_call.function.name,
                                tool_call_id=tool_call.id,
                                content=error_message,
                                tool_result=tool_result,
                            )
                        )
                        tool_message = ChatMessage(
                            role="tool",
                            tool_call_id=tool_call.id,
                            content=f"[TOOL_ERROR] {error_message}",
                        )

                    event_index += 1
                    messages.append(tool_message)
                    self.state.messages.append(tool_message)
                continue

            # 没有 tool_calls 说明模型此轮已经给出了最终回答。
            raw_reply = assistant_msg.get("content", "")
            reply = strip_think(raw_reply)

            events.append(
                AgentEvent(
                    index=event_index,
                    type="final_answer",
                    content=reply,
                )
            )

            assistant_message = ChatMessage(role="assistant", content=raw_reply)
            messages.append(assistant_message)
            self.state.messages.append(assistant_message)
            return AgentOutput(
            reply=reply,  # 最终回复正文
            state=self.state,  # 本轮运行后的最新状态
            events=events,  # 本轮结构化事件列表
            metadata=RunMetadata(
                session_id=agent_input.session_id,  # 先用当前请求的 session_id 填一个最小合法 metadata
            ),  # 这里先保证 AgentOutput 结构合法；真正完整的 metadata 由外层 service 再覆盖
        )
