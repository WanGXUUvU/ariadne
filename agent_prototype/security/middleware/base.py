"""工具调用中间件基础设施。

职责：
- 提供 ToolCallContext 上下文数据载体。
- 提供 BaseMiddleware 抽象基类。
- 提供 MiddlewarePipeline 洋葱圈执行管道。
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolCallContext:
    """工具调用上下文对象"""

    tool_name: str
    tool_args: str
    tool_call_id: str
    session_id: str
    run_id: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)
    """元数据字典，用于不同拦截器之间传递自定义状态或配置"""


class BaseMiddleware(ABC):
    """通用中间件基类（遵循标准的洋葱圈中间件规范）。"""

    @abstractmethod
    async def call(
        self,
        context: Any,
        next_call: Callable[[], Awaitable[Any]],
    ) -> Any:
        """执行中间件拦截或处理逻辑。

        Args:
            context: 任意的数据上下文小车
            next_call: 下一个中间件或终点执行逻辑的异步调用函数
        """
        pass


class MiddlewarePipeline:
    """通用中间件管道执行器，负责把所有中间件像洋葱圈一样套起来执行。"""

    def __init__(self, middlewares: list[BaseMiddleware]):
        """初始化管道，传入中间件列表。"""
        self.middlewares = middlewares

    async def execute(
        self,
        context: Any,
        terminal_call: Callable[[], Awaitable[Any]],
    ) -> Any:
        """启动洋葱圈管道执行，层层深入。"""
        current_call = terminal_call

        def make_next_call(
            middleware: BaseMiddleware,
            next_fn: Callable[[], Awaitable[Any]],
        ) -> Callable[[], Awaitable[Any]]:
            async def wrapped() -> Any:
                logger.debug(f"[Pipeline] 进入中间件: {middleware.__class__.__name__}")
                try:
                    res = await middleware.call(context, next_fn)
                    logger.debug(f"[Pipeline] 退出中间件: {middleware.__class__.__name__}")
                    return res
                except Exception as e:
                    logger.exception(f"[Pipeline] 中件间 {middleware.__class__.__name__} 执行异常: {e}")
                    raise e
            return wrapped

        for middleware in reversed(self.middlewares):
            current_call = make_next_call(middleware, current_call)

        return await current_call()
