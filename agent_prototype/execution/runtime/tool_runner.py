"""应用服务层 (Application Layer) - 工具调用引擎

职责：
1. 驱动大模型解析出的工具（ToolCall）顺序或并发执行。
2. 串联工具执行拦截器管道（ToolInterceptorPipeline），依次执行安全、审批等洋葱圈中间件。

不负责：
1. 物理工具底层逻辑的具体实现。
2. 审批数据的持久化数据库读写。

数据流向：
- 输入：ToolCall 列表入参及执行上下文。
- 输出：包含所有工具返回消息与事件的 ToolBatchResult。
- 上游来源：agent_prototype/execution/runtime/agent_runner.py。
- 下游流向：传递到拦截器中间件管道，并最终分发至 agent_prototype/tools/* 底层方法。
"""

# ── 标准库 ────────────────────────────────────────────────────────────────────
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import AsyncIterator, Optional, Union

# ── 本地模块 ──────────────────────────────────────────────────────────────────
from agent_prototype.core.types import ChatMessage, ToolCall
from agent_prototype.execution.runtime.types import RunEvent
from agent_prototype.execution.runtime.vfs import RunVfsRegistry
from agent_prototype.security.policy.types import ApprovalPolicy
from agent_prototype.tools.registry import ToolRegistry
from agent_prototype.tools.result_types import ToolResult
from agent_prototype.security.middleware.base import MiddlewarePipeline, ToolCallContext
from agent_prototype.security.sandbox.middleware import SandboxMiddleware
from agent_prototype.execution.runtime.tool_batch import build_tool_batch, ToolBatchItem
from agent_prototype.security.approval.checker import needs_approval

# ── 线程池 ────────────────────────────────────────────────────────────────────

# 模块级单例，整个进程共用，超时泄漏的线程也被限在 16 个以内
_tool_thread_pool = ThreadPoolExecutor(
    max_workers=16,
    thread_name_prefix="tool_worker",
)

TOOL_TIMEOUT = 120  # 单次工具调用最长等待秒数


# ── 数据类 ────────────────────────────────────────────────────────────────────

from agent_prototype.execution.runtime.types import ToolBatchResult

# ── 同步工具执行 ──────────────────────────────────────────────────────────────


def handle_tool_calls(
    tool_registry: ToolRegistry,
    tool_calls: list[ToolCall],
    allow_tool_names: Optional[list[str]],
    event_index: int,
    session_id: str = "",
    run_id: Optional[str] = None,
    workspace_path: Optional[str] = None,
) -> ToolBatchResult:
    """同步工具执行器：老老实实、挨个同步去调用大模型想用的那批工具。
    在调用前会进行白名单安全拦截（如果工具不被允许，直接报错）。全部调完后把产生的事件和工具答复包装成结算账单。

    需要拿到的东西：
    - tool_registry: 工具箱仓库（工具注册中心）。
    - tool_calls: 大模型发出的工具调用请求列表。
    - allow_tool_names: 这次允许执行的工具白名单列表（可选）。
    - event_index: 序列号起始索引。

    会给出来的结果：
    - 一个结算账单 ToolBatchResult 对象。
    """
    events: list[RunEvent] = []
    tool_messages: list[ChatMessage] = []
    current_index = event_index

    for tool_call in tool_calls:
        events.append(
            RunEvent(
                index=current_index,
                type="assistant_tool_call",
                tool_name=tool_call.function.name,
                tool_call_id=tool_call.id,
                content=tool_call.function.arguments,
            )
        )
        current_index += 1

        if allow_tool_names is not None and tool_call.function.name not in allow_tool_names:
            raise ValueError(f"Tool not allowed: {tool_call.function.name}")

        # 为同步工具执行构造轻量 Context，确保下沉沙箱生效
        from agent_prototype.security.middleware.base import ToolCallContext
        context = ToolCallContext(
            tool_name=tool_call.function.name,
            tool_args=tool_call.function.arguments,
            tool_call_id=tool_call.id,
            session_id=session_id,
            run_id=run_id,
            workspace_path=workspace_path,
            allow_tool_names=allow_tool_names,
            vfs=RunVfsRegistry.get(run_id) if run_id else None,
        )

        tool_result = tool_registry.execute_tool_call(
            tool_call.function.name,
            tool_call.function.arguments,
            context,
        )

        if tool_result.ok:
            events.append(
                RunEvent(
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
                RunEvent(
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

    return ToolBatchResult(
        events=events,
        tool_messages=tool_messages,
        next_event_index=current_index,
    )


# ── 异步工具执行（含审批与并发） ───────────────────────────────────────────────


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
    session_type: str = "coding",
) -> AsyncIterator[Union[RunEvent, ToolBatchResult]]:
    """异步流式工具执行引擎。

    支持多工具基于 asyncio.gather 并发调度、中间件链执行拦截，
    并在工具全部结束后统一产出 tool_result / tool_error。
    """
    tool_messages: list[ChatMessage] = []
    current_index = event_index

    def approval_checker(tool_name: str) -> bool:
        risk = tool_registry.get_risk_level(tool_name)
        return needs_approval(approval_policy, risk)

    batch = build_tool_batch(
        run_id=run_id,
        batch_id=f"{run_id}:step:{event_index}",
        tool_calls=tool_calls,
        approval_checker=approval_checker,
    )
    ready_items = []
    pending_items = []

    for item in batch.items:
        if item.requires_approval:
            pending_items.append(item)
        else:
            ready_items.append(item)

    # 1. 播报：本轮要调用哪些工具
    for item in batch.items:
        yield RunEvent(
            index=current_index,
            type="assistant_tool_call",
            tool_name=item.tool_name,
            tool_call_id=item.tool_call_id,
            content=item.arguments,
        )
        current_index += 1

    # 2. 初始化中间件管道
    if session_type == "coding":
        pipeline = MiddlewarePipeline([SandboxMiddleware()])
    else:
        pipeline = MiddlewarePipeline([])

    # 3. 定义单个工具的执行协程 Worker
    async def run_single_tool(item: ToolBatchItem):
        context = ToolCallContext(
            tool_name=item.tool_name,
            tool_args=item.arguments,
            tool_call_id=item.tool_call_id,
            session_id=session_id,
            run_id=run_id,
            workspace_path=workspace_path,
            allow_tool_names=allow_tool_names,
            vfs=RunVfsRegistry.get(run_id) if run_id else None,
        )

        async def terminal_execute_call() -> ToolResult:
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
                        context,
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
                on_tool_finish(record_id, finish_status, res.content if res else None)

            return res

        res = await pipeline.execute(context, terminal_execute_call)
        return res

    # 4. 封装并发 Task 集合并启动
    tasks = []
    for item in ready_items:
        task = asyncio.create_task(run_single_tool(item))
        tasks.append(task)

    try:
        results = await asyncio.gather(*tasks)
    except Exception as exc:
        for task in tasks:
            if not task.done():
                task.cancel()
        raise exc

    # 5. 并发结束，按时序合并输出最终卡片
    for item, tool_result in zip(ready_items, results):
        if tool_result is None:
            error_message = f"Tool timed out after {TOOL_TIMEOUT}s"
            yield RunEvent(
                index=current_index,
                type="tool_error",
                tool_name=item.tool_name,
                tool_call_id=item.tool_call_id,
                content=error_message,
            )
            tool_message = ChatMessage(
                role="tool",
                tool_call_id=item.tool_call_id,
                content=f"[TOOL_TIMEOUT] {error_message}",
            )
            item.result_message = tool_message
            tool_messages.append(tool_message)
        elif tool_result.ok:
            yield RunEvent(
                index=current_index,
                type="tool_result",
                tool_name=item.tool_name,
                tool_call_id=item.tool_call_id,
                content=tool_result.content,
                tool_result=tool_result,
            )
            tool_message = ChatMessage(
                role="tool",
                tool_call_id=item.tool_call_id,
                content=tool_result.content,
            )
            item.result_message = tool_message
            tool_messages.append(tool_message)
        elif tool_result.error:
            error_message = tool_result.error.message if tool_result.error.message else "Tool failed"
            yield RunEvent(
                index=current_index,
                type="tool_error",
                tool_name=item.tool_name,
                tool_call_id=item.tool_call_id,
                content=error_message,
                tool_result=tool_result,
            )
            tool_message = ChatMessage(
                role="tool",
                tool_call_id=item.tool_call_id,
                content=f"[TOOL_ERROR] {error_message}",
            )
            item.result_message = tool_message
            tool_messages.append(tool_message)
        current_index += 1

    if pending_items:
        approval_saved_messages = list(saved_messages or []) + tool_messages

        for item in pending_items:
            approval_id = None
            if on_approval_required:
                approval_id = on_approval_required(
                    item.tool_call_id,
                    item.tool_name,
                    item.arguments,
                    approval_saved_messages,
                    current_index,
                    batch.batch_id,
                )
            item.approval_id = approval_id or item.arguments
            yield RunEvent(
                index=current_index,
                type="approval_required",
                tool_name=item.tool_name,
                tool_call_id=item.tool_call_id,
                content=item.approval_id,
            )
            current_index += 1

        yield ToolBatchResult(
            tool_messages=tool_messages,  # 这里只含 ready items 的结果
            next_event_index=current_index,
            paused_for_approval=True,
        )
        return

    yield ToolBatchResult(
        tool_messages=tool_messages,
        next_event_index=current_index,
    )
