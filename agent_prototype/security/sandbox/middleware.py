"""物理安全沙箱隔离与工作区虚拟化中间件。"""

import json
import logging
from pathlib import Path
from typing import Awaitable, Callable

from agent_prototype.security.middleware.base import BaseMiddleware, ToolCallContext
from agent_prototype.tools.result_types import ToolResult, ToolError

logger = logging.getLogger(__name__)


class SandboxMiddleware(BaseMiddleware):
    """沙箱与工作区虚拟投影中间件。

    这个类是一个“路径沙箱安检站（沙箱隔离中间件）”。
    它主要有两个非常硬核的任务：
    1. 【工具准入校验】：检查 AI 调用的工具，是不是当前 Agent 获准使用的白名单工具。如果 AI 偷偷用了不该用的工具，直接拦截并报错“TOOL_NOT_ALLOWED”。
    2. 【沙箱防越界逃逸】：如果当前会话绑定了一个工作区（文件夹），它会把 AI 填的所有文件/文件夹路径（比如 `/src/main.py` 或 `../escape.txt`）全部强制“投影映射”到工作区文件夹内，并且严格检查。一旦发现 AI 试图用 `..` 相对路径逃逸出工作区去读取你电脑上的敏感系统文件，它就会雷霆拦截，并报出“SANDBOX_VIOLATION（沙箱越界违规）”错误，保护用户电脑的安全。
    """

    async def call(
        self,
        context: ToolCallContext,
        next_call: Callable[[], Awaitable[ToolResult]],
    ) -> ToolResult:
        """这是沙箱安检站的具体检查流程。
        它会先验一验工具是否准入；如果通过了，且绑定了工作区，它就会把工具入参里的所有路径参数都抓出来进行“绝对化 resolve 投影匹配”和改写，确保它们无论如何都逃不出工作区的五指山。完全放行后，把修改为物理绝对路径的参数写回小车，并叫起下一关。

        需要拿到的东西：
        - context (ToolCallContext): 装满工具调用数据的“安检小推车”。
        - next_call (Callable): 下一个关卡放行通行证函数。

        会给出来的结果：
        - ToolResult: 工具的运行结果。如果在准入检查或沙箱路径防逃逸检查中露出了马脚，它会直接返回一个 ok=False 且包含具体安全违规错误码的结果包，不再继续往下走。
        """
        logger.info(f"[SandboxMiddleware] 正在执行工具白名单与路径沙箱校验: {context.tool_name}...")

        # 1. ：工具名称准入校验 (AOP Tool Restriction)
        allow_tool_names = context.extra.get("allow_tool_names")
        if allow_tool_names is not None and context.tool_name not in allow_tool_names:
            logger.warning(f"[SandboxMiddleware] 工具未被当前 Agent 允许调用: {context.tool_name}")
            return ToolResult(
                ok=False,
                content=None,
                error=ToolError(
                    code="TOOL_NOT_ALLOWED",
                    tool_name=context.tool_name,
                    message=f"Tool '{context.tool_name}' is not allowed by this agent.",
                ),
            )

        # 2. 读取物理工作区路径
        workspace_path = context.extra.get("workspace_path")
        if not workspace_path:
            return await next_call()

        # 3. 直接委派给公共 SandboxPathResolver 校验并重写
        from agent_prototype.security.sandbox.resolver import SandboxPathResolver
        ok, modified_args, err_msg = SandboxPathResolver.resolve_and_rewrite(
            context.tool_name, context.tool_args, workspace_path
        )
        if not ok:
            return ToolResult(
                ok=False,
                content=None,
                error=ToolError(
                    code="SANDBOX_VIOLATION",
                    tool_name=context.tool_name,
                    message=err_msg or "Sandbox Violation",
                ),
            )

        context.tool_args = modified_args
        return await next_call()
