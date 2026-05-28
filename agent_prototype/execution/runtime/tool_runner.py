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
from agent_prototype.core.types import AgentEvent
from agent_prototype.core.types import ChatMessage, RiskLevel, ToolCall, ToolResult
from agent_prototype.security.policy import ApprovalPolicy
from agent_prototype.security.approval.checker import needs_approval
from agent_prototype.tools.registry import ToolRegistry
from agent_prototype.security.middleware.base import MiddlewarePipeline
from agent_prototype.security.types import ToolCallContext
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

from agent_prototype.execution.runtime.types import ToolTurnResult

# ── 同步工具执行 ──────────────────────────────────────────────────────────────

def handle_tool_calls(
    tool_registry: ToolRegistry,
    tool_calls: list[ToolCall],
    allow_tool_names: Optional[list[str]],
    event_index: int,
) -> ToolTurnResult:
    """同步工具执行器：老老实实、挨个同步去调用大模型想用的那批工具。
    在调用前会进行白名单安全拦截（如果工具不被允许，直接报错）。全部调完后把产生的事件和工具答复包装成结算账单。

    需要拿到的东西：
    - tool_registry: 工具箱仓库（工具注册中心）。
    - tool_calls: 大模型发出的工具调用请求列表。
    - allow_tool_names: 这次允许执行的工具白名单列表（可选）。
    - event_index: 序列号起始索引。

    会给出来的结果：
    - 一个结算账单 ToolTurnResult 对象。
    """
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
    """异步流式工具执行器（超强安全大洋葱！）：支持异步并发、支持复杂的洋葱拦截器中间件链（例如沙箱运行 SandboxMiddleware 和人工审批 ApprovalMiddleware）。
    在异步执行过程中，如果遇到敏感操作（触发了审批规则），它会抛出异常中断执行，并以 `approval_required` 事件形式实时 yield 出来通知前端，
    然后暂停，等人类来审批。如果没有遇到阻碍，就会默默在线程池里安全完成调用。

    需要拿到的东西：
    - tool_registry: 工具箱仓库。
    - tool_calls: 待调用的工具列表。
    - allow_tool_names: 工具白名单。
    - event_index: 序列号起始索引。
    - session_id: 当前会话的 ID。
    - run_id: 运行的唯一 ID。
    - workspace_path: 工作区物理路径（用于沙箱环境隔离，可选）。
    - on_tool_start: 工具启动时的回调跟踪（可选）。
    - on_tool_finish: 工具结束时的回调跟踪（可选）。
    - approval_policy: 审批策略。
    - on_approval_required: 触发审批时的回调（可选）。
    - saved_messages: 历史消息快照（用于审批现场还原，可选）。
    - session_type: 会话类型（默认 "coding"）。

    会给出来的结果：
    - 一个异步生成器，会实时 yield 智能体事件（AgentEvent）或者最终结算账单（ToolTurnResult）。
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
