"""工具调用中间件基础设施。

职责：
- 提供 ToolCallContext 上下文数据载体。
- 提供 BaseMiddleware 抽象基类。
- 提供 MiddlewarePipeline 洋葱圈执行管道。
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolCallContext:
    """工具调用上下文对象，作为安全中间件与工具之间的数据流转载体。

    这个对象的定位不是“整次 run 的上下文”，而是“单次 tool call 的执行上下文”。
    它会一路经过 middleware pipeline，最后传到具体工具实现。
    """

    # 本次调用的工具名，例如 read_file / write_file。
    tool_name: str
    # 模型生成的原始 arguments 字符串，尚未被工具层解析前的形态。
    tool_args: str
    # 模型为这次 tool call 分配的唯一 ID。
    tool_call_id: str
    # tool call 所属 session。
    session_id: str
    # tool call 所属 run；用于 VFS、trace、审批恢复等跨层关联。
    run_id: Optional[str] = None
    # 物理工作区路径；registry 基于它做路径解析和沙箱投影。
    workspace_path: Optional[str] = None
    # 当前 agent 允许调用的工具白名单；SandboxMiddleware 使用。
    allow_tool_names: Optional[list[str]] = None
    # 当前 run 的内存 VFS；文件工具读写会优先走它。
    vfs: Optional[Any] = None


class BaseMiddleware(ABC):
    """通用安全中间件基类，派生类需遵循洋葱圈规范。"""

    @abstractmethod
    async def call(
        self,
        context: Any,
        next_call: Callable[[], Awaitable[Any]],
    ) -> Any:
        """中间件的核心拦截逻辑入口。

        在内部可以通过检查 context 决定是否放行（调用 next_call）或阻断执行。
        """
        pass


class MiddlewarePipeline:
    """通用中间件管道执行器，支持以洋葱圈模型嵌套执行所有注册的拦截器。"""

    def __init__(self, middlewares: list[BaseMiddleware]):
        self.middlewares = middlewares

    async def execute(
        self,
        context: Any,
        terminal_call: Callable[[], Awaitable[Any]],
    ) -> Any:
        """按照逆序依次组装洋葱圈，并在最里层执行物理工具函数。"""
        current_call = terminal_call

        def make_next_call(
            middleware: BaseMiddleware,
            next_fn: Callable[[], Awaitable[Any]],
        ) -> Callable[[], Awaitable[Any]]:
            async def wrapped() -> Any:
                logger.debug(f"[Pipeline] 进入中间件: {middleware.__class__.__name__}")
                try:
                    res = await middleware.call(context, next_fn)
                    logger.debug(
                        f"[Pipeline] 退出中间件: {middleware.__class__.__name__}"
                    )
                    return res
                except Exception as e:
                    logger.exception(
                        f"[Pipeline] 中件间 {middleware.__class__.__name__} 执行异常: {e}"
                    )
                    raise e

            return wrapped

        for middleware in reversed(self.middlewares):
            current_call = make_next_call(middleware, current_call)

        return await current_call()
