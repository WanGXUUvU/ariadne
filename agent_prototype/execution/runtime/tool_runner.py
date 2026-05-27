"""应用服务层 (Application Layer) - 工具调用引擎

职责：
1. 驱动大模型解析出的工具（ToolCall）顺序或并发执行。
2. 串联工具执行拦截器管道（ToolInterceptorPipeline），依次执行安全、审批等洋葱圈中间件。

不负责：
1. 物理工具底层逻辑的具体实现。
2. 审批数据的持久化数据库读写。

数据流向：
- 输入：ToolCall 列表入参及执行上下文。
- 输出：包含所有工具返回消息与事件的 ToolTurnResult。
- 上游来源：agent_prototype/execution/runtime/agent_runtime.py。
- 下游流向：传递到拦截器中间件管道，并最终分发至 agent_prototype/tools/* 底层方法。
"""

# ── 标准库 ────────────────────────────────────────────────────────────────────
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import AsyncIterator, Optional, Union
# ── 本地模块 ──────────────────────────────────────────────────────────────────
from agent_prototype.api.dto.schemas import (
    AgentEvent, ApprovalPolicy, ChatMessage, RiskLevel, ToolCall, ToolResult, needs_approval
)
from agent_prototype.tools.registry import ToolRegistry
from agent_prototype.security.middleware.base import MiddlewarePipeline
from agent_prototype.security.middleware.base import ToolCallContext
from agent_prototype.security.sandbox.middleware import SandboxMiddleware
from agent_prototype.security.approval.middleware import ApprovalMiddleware, ApprovalRequiredException

# ── 线程池 ────────────────────────────────────────────────────────────────────

# 模块级单例，整个进程共用，超时泄漏的线程也被限在 16 个以内
_tool_thread_pool = ThreadPoolExecutor(
    max_workers=16,
    thread_name_prefix="tool_worker",
)

TOOL_TIMEOUT = 120  # 单次工具调用最长等待秒数


# ── 数据类 ────────────────────────────────────────────────────────────────────

@dataclass
class ToolTurnResult:
    """一次 tool call 批处理后的结果。"""

    events: list[AgentEvent]
    tool_messages: list[ChatMessage]
    next_event_index: int
    paused_for_approval: bool = False

# ── 同步工具执行 ──────────────────────────────────────────────────────────────

def handle_tool_calls(
    tool_registry: ToolRegistry,
    tool_calls: list[ToolCall],
    allow_tool_names: Optional[list[str]],
    event_index: int,
) -> ToolTurnResult:
    """同步处理一轮模型返回的 tool calls。"""
    events: list[AgentEvent] = []
    tool_messages: list[ChatMessage] = []
    current_index = event_index

    for tool_call in tool_calls:
        events.append(AgentEvent(
            index=current_index,
            type="assistant_tool_call",
            tool_name=tool_call.function.name,
            tool_call_id=tool_call.id,
            content=tool_call.function.arguments,
        ))
        current_index += 1

        if allow_tool_names is not None and tool_call.function.name not in allow_tool_names:
            raise ValueError(f"Tool not allowed: {tool_call.function.name}")

        tool_result = tool_registry.execute_tool_call(
            tool_call.function.name,
            tool_call.function.arguments,
        )

        if tool_result.ok:
            events.append(AgentEvent(
                index=current_index,
                type="tool_result",
                tool_name=tool_call.function.name,
                tool_call_id=tool_call.id,
                content=tool_result.content,
                tool_result=tool_result,
            ))
            tool_message = ChatMessage(
                role="tool",
                tool_call_id=tool_call.id,
                content=tool_result.content,
            )
        else:
            error_message = tool_result.error.message if tool_result.error else "Tool failed"
            events.append(AgentEvent(
                index=current_index,
                type="tool_error",
                tool_name=tool_call.function.name,
                tool_call_id=tool_call.id,
                content=error_message,
                tool_result=tool_result,
            ))
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


# ── 异步工具执行（含审批） ─────────────────────────────────────────────────────

async def async_handle_tool_calls(
    tool_registry: ToolRegistry,
    tool_calls: list[ToolCall],
    allow_tool_names: Optional[list[str]],
    event_index: int,
    session_id: str,
    run_id: str,
    workspace_path: Optional[str] = None,
    on_tool_start=None,
    on_tool_finish=None,
    approval_policy: ApprovalPolicy = ApprovalPolicy.NEVER,
    on_approval_required=None,
    saved_messages: Optional[list[ChatMessage]] = None,
    session_type:str="coding",
) -> AsyncIterator[Union[AgentEvent, ToolTurnResult]]:
    """异步处理一轮 tool calls，支持审批中断。

    逐条 yield AgentEvent 或最终 ToolTurnResult。
    """
    tool_messages: list[ChatMessage] = []
    current_index = event_index
    if session_type=="coding":
    #初始化洋葱中间件管道
        pipeline = MiddlewarePipeline([
            SandboxMiddleware(),
            ApprovalMiddleware(),
        ])
    else:
        pipeline=MiddlewarePipeline([ApprovalMiddleware])
        
    for tool_call in tool_calls:
        yield AgentEvent(
            index=current_index,
            type="assistant_tool_call",
            tool_name=tool_call.function.name,
            tool_call_id=tool_call.id,
            content=tool_call.function.arguments,
        )
        current_index += 1
        risk=tool_registry.get_risk_level(tool_call.function.name)
        context=ToolCallContext(
            tool_name=tool_call.function.name,
            tool_args=tool_call.function.arguments,
            tool_call_id=tool_call.id,
            session_id=session_id,
            run_id=run_id,
            extra={
                "workspace_path":workspace_path,
                "allow_tool_names":allow_tool_names,
                "risk_level":risk,
                "on_approval_required":on_approval_required,
                "saved_messages":saved_messages,
                "current_index":current_index,
                "approval_policy": approval_policy,
            }

        )
        async def terminal_execute_call()->ToolResult:
            # ── 工具执行 ──────────────────────────────────────────────────────────
            record_id = None
            if on_tool_start:
                record_id = on_tool_start(
                    context.tool_name,
                    context.tool_call_id,
                    context.tool_args,
                )

            try:
                loop = asyncio.get_event_loop()
                res = await asyncio.wait_for(
                    loop.run_in_executor(
                        _tool_thread_pool,
                        tool_registry.execute_tool_call,
                        context.tool_name,
                        context.tool_args,
                    ),
                    timeout=TOOL_TIMEOUT,
                )
                finish_status = "completed" if res.ok else "failed"

            except asyncio.TimeoutError:
                res = None
                finish_status = "timeout"

            except Exception:
                res = None
                finish_status = "failed"

            if on_tool_finish and record_id is not None:
                on_tool_finish(
                    record_id,
                    finish_status,
                    res.content if res else None,
                )
            return res
        try:
            tool_result = await pipeline.execute(context, terminal_execute_call)
        except ApprovalRequiredException as exc:
            yield AgentEvent(
                index=current_index,
                type="approval_required",
                tool_name=context.tool_name,
                tool_call_id=context.tool_call_id,
                content=exc.approval_id,
            )
            current_index += 1
            yield ToolTurnResult(
                events=[],
                tool_messages=[],
                next_event_index=current_index,
                paused_for_approval=True,
            )
            return

        if tool_result is None:
            error_message = f"Tool timed out after {TOOL_TIMEOUT}s"
            yield AgentEvent(
                index=current_index,
                type="tool_error",
                tool_name=tool_call.function.name,
                tool_call_id=tool_call.id,
                content=error_message,
            )
            tool_messages.append(ChatMessage(
                role="tool",
                tool_call_id=tool_call.id,
                content=f"[TOOL_TIMEOUT] {error_message}",
            ))
            current_index += 1
            continue

        if tool_result.ok:
            yield AgentEvent(
                index=current_index,
                type="tool_result",
                tool_name=tool_call.function.name,
                tool_call_id=tool_call.id,
                content=tool_result.content,
                tool_result=tool_result,
            )
            tool_messages.append(ChatMessage(
                role="tool",
                tool_call_id=tool_call.id,
                content=tool_result.content,
            ))
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
            tool_messages.append(ChatMessage(
                role="tool",
                tool_call_id=tool_call.id,
                content=f"[TOOL_ERROR] {error_message}",
            ))

        current_index += 1

    yield ToolTurnResult(
        events=[],
        tool_messages=tool_messages,
        next_event_index=current_index,
    )
