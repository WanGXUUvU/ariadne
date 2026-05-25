"""物理安全沙箱隔离与工作区虚拟化中间件。"""

import json
import logging
from pathlib import Path
from typing import Awaitable, Callable

from agent_prototype.core.schemas import ToolResult, ToolError
from agent_prototype.core.middleware import BaseMiddleware
from agent_prototype.application.runtime.middleware.base import ToolCallContext

logger = logging.getLogger(__name__)


class SandboxMiddleware(BaseMiddleware):
    """沙箱与工作区虚拟投影中间件。
    
    职责：
    1. 校验工具名称是否属于当前 Agent 的 allow_tool_names 允许列表，未准入则优雅返回 TOOL_NOT_ALLOWED；
    2. 若未绑定工作区，视为全局模式，直接放行；
    3. 若绑定工作区，将工具路径入参自动映射为工作区内的物理路径，并严格执行越界防御；
    4. 对合法路径执行参数改写，写回小推车。
    """

    async def call(
        self,
        context: ToolCallContext,
        next_call: Callable[[], Awaitable[ToolResult]],
    ) -> ToolResult:
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
                    message=f"Tool '{context.tool_name}' is not allowed by this agent."
                )
            )

        # 2. 读取物理工作区路径
        workspace_path = context.extra.get("workspace_path")
        if not workspace_path:
            return await next_call()

        # 3. 解析工具入参 JSON，执行工作区虚拟投影与参数改写
        try:
            args = json.loads(context.tool_args)
        except Exception:
            args = {}

        path_keys = {"path", "file_path", "dir_path", "filename", "filepath", "directory"}
        sandbox_root = Path(workspace_path).resolve()
        modified = False

        for k, v in args.items():
            if k in path_keys and isinstance(v, str):
                p_str = v.strip()
                
                # 路径解析：绝对路径直接 resolve，相对路径拼接工作区根再 resolve
                p_path = Path(p_str)
                if p_path.is_absolute():
                    resolved_p = p_path.resolve()
                else:
                    # 相对路径 (例如 src/App.vue 或 ../etc/passwd)
                    resolved_p = (sandbox_root / p_str).resolve()

                # 物理路径防越界逃逸 (使用 parents 关系判断，防止前缀相似漏洞)
                is_inside = (sandbox_root in resolved_p.parents) or (resolved_p == sandbox_root)
                if not is_inside:
                    logger.error(f"[SandboxMiddleware] 沙箱安全拦截！路径越界逃逸: {v} -> {resolved_p}")
                    return ToolResult(
                        ok=False,
                        content=None,
                        error=ToolError(
                            code="SANDBOX_VIOLATION",
                            tool_name=context.tool_name,
                            message=f"Sandbox Violation: Path '{v}' resolves outside the workspace '{sandbox_root}'."
                        )
                    )

                args[k] = str(resolved_p)
                modified = True

        if modified:
            context.tool_args = json.dumps(args)
            logger.info(f"[SandboxMiddleware] 工作区投影映射成功，参数改写为: {context.tool_args}")

        return await next_call()