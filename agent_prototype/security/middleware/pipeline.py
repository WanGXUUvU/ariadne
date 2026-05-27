"""通用洋葱圈中间件管道地基。

职责：
- 提供 BaseMiddleware 抽象基类。
- 提供 MiddlewarePipeline 通用洋葱圈执行管道。
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


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
                    # 在底层只记录异常，将异常向上抛出，由特定领域中间件自己去包裹特殊的报错类型
                    raise e
            return wrapped

        # 从后往前套娃包裹
        for middleware in reversed(self.middlewares):
            current_call = make_next_call(middleware, current_call)

        return await current_call()