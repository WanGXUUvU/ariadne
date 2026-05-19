from dataclasses import dataclass
from typing import Optional,AsyncIterator,Union
import asyncio

from ..core.schemas import AgentEvent, ChatMessage, ToolCall,ApprovalPolicy,RiskLevel
from ..tools.tool_registry import ToolRegistry
from concurrent.futures import ThreadPoolExecutor

# 模块级，只创建一次，整个进程共用这一个池
_tool_thread_pool = ThreadPoolExecutor(
    max_workers=16,                    # 最多同时 16 个工具在跑，超时泄漏的线程也被限在 16 个以内
    thread_name_prefix="tool_worker",  # 调试时 ps/top 里能看到线程名，方便排查
)

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

def needs_approval(policy:ApprovalPolicy,risk:RiskLevel)->bool:
    if policy == ApprovalPolicy.NEVER:
        return False
    if policy==ApprovalPolicy.UNTRUSTED:
        return risk !=RiskLevel.SAFE
    if policy == ApprovalPolicy.ON_REQUEST:
        return risk==RiskLevel.DANGER
    return False

async def async_handle_tool_calls(
    tool_registry: ToolRegistry,
    tool_calls: list[ToolCall],
    allow_tool_names: Optional[list[str]],
    event_index: int,
    on_tool_start=None,
    on_tool_finish=None,
    approval_policy:ApprovalPolicy=ApprovalPolicy.NEVER,
    on_approval_required=None,
) -> AsyncIterator[Union[AgentEvent, ToolTurnResult]]:
    """处理一轮模型返回的 tool calls。 AsyncIterator 是告诉类型检查器"这个函数会逐条产出 AgentEvent 或 ToolTurnResult"""

    tool_messages: list[ChatMessage] = []
    current_index = event_index

    for tool_call in tool_calls:
        yield AgentEvent(
            index=current_index,
            type="assistant_tool_call",
            tool_name=tool_call.function.name,
            tool_call_id=tool_call.id,
            content=tool_call.function.arguments,
        )
        current_index += 1

        if allow_tool_names is not None and tool_call.function.name not in allow_tool_names:
            raise ValueError(f"Tool not allowed:{tool_call.function.name}")
        
        record_id=None
        risk = tool_registry.get_risk_level(tool_call.function.name)

        if needs_approval(approval_policy,risk):
            approval_id = None
            if on_approval_required:
                approval_id = on_approval_required(
                    tool_call.function.name,
                    tool_call.function.arguments,
                )
            yield AgentEvent(
                index=current_index,
                type="approval_required",
                tool_name=tool_call.function.name,
                tool_call_id=tool_call.id,
                content=approval_id or tool_call.function.arguments,
            )
            current_index+=1
            continue
        if on_tool_start:
            record_id=on_tool_start(
                tool_call.function.name,
                tool_call.id,
                tool_call.function.arguments,
            )
        TOOL_TIMEOUT=120
        try:
        #asyncio.to_thread 的意思是：把这个同步函数丢到另一个线程去跑，主线程不等它，事件循环继续转。
            # tool_result = await asyncio.wait_for(
            #     asyncio.to_thread(
            #     tool_registry.execute_tool_call,
            #     tool_call.function.name,
            #     tool_call.function.arguments,
            #     ),
            #     timeout=TOOL_TIMEOUT,
            # )
            #两者功能完全一样，区别只是线程池是谁的。
            loop = asyncio.get_event_loop()   # 拿到当前的事件循环对象
            tool_result = await asyncio.wait_for(
                loop.run_in_executor(
                    _tool_thread_pool,            # ← 指定用我们自己的池
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

        except Exception:
            tool_result=None
            finish_status="failed"

        if on_tool_finish and record_id is not None:
            on_tool_finish(
                record_id,
                finish_status,
                tool_result.content if tool_result else None,
            )

        if tool_result is None:
            error_message = f"Tool timed out after {TOOL_TIMEOUT}s"
            yield AgentEvent(
                index=current_index,
                type="tool_error",
                tool_name=tool_call.function.name,
                tool_call_id=tool_call.id,
                content=error_message,
            )
            tool_message = ChatMessage(
                role="tool",
                tool_call_id=tool_call.id,
                content=f"[TOOL_TIMEOUT] {error_message}",
            )
            current_index += 1
            tool_messages.append(tool_message)
            continue  # 这个工具超时，继续处理下一个


        if tool_result.ok:
            yield AgentEvent(
                    index=current_index,
                    type="tool_result",
                    tool_name=tool_call.function.name,
                    tool_call_id=tool_call.id,
                    content=tool_result.content,
                    tool_result=tool_result,
                )

            tool_message = ChatMessage(
                role="tool",
                tool_call_id=tool_call.id,
                content=tool_result.content,
            )
        else:
            error_message = tool_result.error.message if tool_result.error else "Tool failed"
            yield AgentEvent(
                    index=current_index,
                    type="tool_error",
                    tool_name=tool_call.function.name,
                    tool_call_id=tool_call.id,
                    content=error_message,
                    tool_result=tool_result,
                )
            tool_message = ChatMessage(
                role="tool",
                tool_call_id=tool_call.id,
                content=f"[TOOL_ERROR] {error_message}",
            )
        current_index += 1
        tool_messages.append(tool_message)

    yield ToolTurnResult(
        events=[],
        tool_messages=tool_messages,
        next_event_index=current_index,
    )

# 用户点了 Stop 按钮 → 前端关闭 SSE 连接
# → FastAPI 检测到 disconnect
# → 触发 asyncio.CancelledError
# → async_stream_run 的 await 点收到取消信号
# → 工具执行停止（线程还在跑，但结果不再被用）
# → finally 块执行，保存 partial_reply