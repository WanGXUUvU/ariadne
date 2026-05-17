from dataclasses import dataclass
from typing import Optional
import asyncio

from ..core.schemas import AgentEvent, ChatMessage, ToolCall
from ..tools.tool_registry import ToolRegistry


@dataclass
class ToolTurnResult:
    """一次 tool call 批处理后的结果。"""

    events: list[AgentEvent]
    tool_messages: list[ChatMessage]
    next_event_index: int


def handle_tool_calls(
    tool_registry: ToolRegistry,
    tool_calls: list[ToolCall],
    allow_tool_names: Optional[list[str]],
    event_index: int,
) -> ToolTurnResult:
    """处理一轮模型返回的 tool calls。"""

    events: list[AgentEvent] = []
    tool_messages: list[ChatMessage] = []
    current_index = event_index

    for tool_call in tool_calls:
        events.append(
            AgentEvent(
                index=current_index,
                type="assistant_tool_call",
                tool_name=tool_call.function.name,
                tool_call_id=tool_call.id,
                content=tool_call.function.arguments,
            )
        )
        current_index += 1

        if allow_tool_names is not None and tool_call.function.name not in allow_tool_names:
            raise ValueError(f"Tool not allowed:{tool_call.function.name}")

        tool_result = tool_registry.execute_tool_call(
            tool_call.function.name,
            tool_call.function.arguments,
        )

        if tool_result.ok:
            events.append(
                AgentEvent(
                    index=current_index,
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
                    index=current_index,
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
        current_index += 1
        tool_messages.append(tool_message)

    return ToolTurnResult(
        events=events,
        tool_messages=tool_messages,
        next_event_index=current_index,
    )

async def async_handle_tool_calls(
    tool_registry: ToolRegistry,
    tool_calls: list[ToolCall],
    allow_tool_names: Optional[list[str]],
    event_index: int,
    on_tool_start=None,
    on_tool_finish=None,
) -> ToolTurnResult:
    """处理一轮模型返回的 tool calls。"""

    events: list[AgentEvent] = []
    tool_messages: list[ChatMessage] = []
    current_index = event_index

    for tool_call in tool_calls:
        events.append(
            AgentEvent(
                index=current_index,
                type="assistant_tool_call",
                tool_name=tool_call.function.name,
                tool_call_id=tool_call.id,
                content=tool_call.function.arguments,
            )
        )
        current_index += 1

        if allow_tool_names is not None and tool_call.function.name not in allow_tool_names:
            raise ValueError(f"Tool not allowed:{tool_call.function.name}")
        
        record_id=None
        if on_tool_start:
            record_id=on_tool_start(
                tool_call.function.name,
                tool_call.id,
                tool_call.function.arguments,
            )
        TOOL_TIMEOUT=30
        try:
        #asyncio.to_thread 的意思是：把这个同步函数丢到另一个线程去跑，主线程不等它，事件循环继续转。
            tool_result = await asyncio.wait_for(
                asyncio.to_thread(
                tool_registry.execute_tool_call,
                tool_call.function.name,
                tool_call.function.arguments,
                ),
                timeout=TOOL_TIMEOUT,
            )
            finish_status="completed" if tool_result.ok else "failed"
        
        except asyncio.TimeoutError:
            tool_result=None
            finish_status="timeout"
        
        if on_tool_finish and record_id is not None:
            on_tool_finish(
                record_id,
                finish_status,
                tool_result.content if tool_result else None,
            )

        if tool_result is None:
            error_message = f"Tool timed out after {TOOL_TIMEOUT}s"
            events.append(AgentEvent(
                index=current_index,
                type="tool_error",
                tool_name=tool_call.function.name,
                tool_call_id=tool_call.id,
                content=error_message,
            ))
            tool_message = ChatMessage(
                role="tool",
                tool_call_id=tool_call.id,
                content=f"[TOOL_TIMEOUT] {error_message}",
            )
            current_index += 1
            tool_messages.append(tool_message)
            continue  # 这个工具超时，继续处理下一个


        if tool_result.ok:
            events.append(
                AgentEvent(
                    index=current_index,
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
                    index=current_index,
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
        current_index += 1
        tool_messages.append(tool_message)

    return ToolTurnResult(
        events=events,
        tool_messages=tool_messages,
        next_event_index=current_index,
    )

# 用户点了 Stop 按钮 → 前端关闭 SSE 连接
# → FastAPI 检测到 disconnect
# → 触发 asyncio.CancelledError
# → async_stream_run 的 await 点收到取消信号
# → 工具执行停止（线程还在跑，但结果不再被用）
# → finally 块执行，保存 partial_reply