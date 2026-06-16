"""工具调用沙箱中间件。"""

import logging
from typing import Awaitable, Callable

from agent_prototype.security.middleware.base import BaseMiddleware, ToolCallContext
from agent_prototype.tools.result_types import ToolResult, ToolError

logger = logging.getLogger(__name__)


class SandboxMiddleware(BaseMiddleware):
    """工具沙箱中间件。

    当前职责只保留工具白名单准入校验。
    路径投影与越界校验统一下沉到 ToolRegistry.execute_tool_call，
    避免 middleware 与 registry 双重 rewrite 同一路径。
    """

    async def call(
        self,
        context: ToolCallContext,
        next_call: Callable[[], Awaitable[ToolResult]],
    ) -> ToolResult:
        """执行工具白名单校验并放行到下一层。

        需要拿到的东西：
        - context (ToolCallContext): 装满工具调用数据的“安检小推车”。
        - next_call (Callable): 下一个关卡放行通行证函数。

        会给出来的结果：
        - ToolResult: 工具的运行结果。如果工具未被允许，会直接返回
        TOOL_NOT_ALLOWED；否则原样放行。
        """
        logger.info(
            f"[SandboxMiddleware] 正在执行工具白名单校验: {context.tool_name}..."
        )

        # 1. ：工具名称准入校验 (AOP Tool Restriction)
        allow_tool_names = context.allow_tool_names
        if allow_tool_names is not None and context.tool_name not in allow_tool_names:
            logger.warning(
                f"[SandboxMiddleware] 工具未被当前 Agent 允许调用: {context.tool_name}"
            )
            return ToolResult(
                ok=False,
                content=None,
                error=ToolError(
                    code="TOOL_NOT_ALLOWED",
                    tool_name=context.tool_name,
                    message=f"Tool '{context.tool_name}' is not allowed by this agent.",
                ),
            )

        return await next_call()
