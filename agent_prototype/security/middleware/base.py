"""工具调用中间件基础设施。

职责：
- 提供 ToolCallContext 上下文数据载体。
- 提供 BaseMiddleware 抽象基类。
- 提供 MiddlewarePipeline 洋葱圈执行管道。
"""

import logging
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolCallContext:
    """工具调用上下文对象，作为安全中间件与工具之间的数据流转载体。"""

    tool_name: str
    tool_args: str
    tool_call_id: str
    session_id: str
    run_id: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)
    """元数据字典，用于中间件之间传递共享状态或参数"""

    on_progress: Optional[Callable[[str], Awaitable[None]]] = None
    """流式进度回调函数，用于实时向主线程投递进度事件"""

    loop: Optional[asyncio.AbstractEventLoop] = None
    """主事件循环，用以支持多线程/同步物理工具环境下的线程安全进度投递"""

    def emit_progress(self, text: str) -> None:
        """物理工具在执行期间，通过此接口主动触发上报流式进度。

        如果存在绑定的 on_progress 回调和活动事件循环，将以线程安全的方式提交给主线程执行。
        """
        if self.on_progress and self.loop:
            if self.loop.is_running():
                asyncio.run_coroutine_threadsafe(self.on_progress(text), self.loop)


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
                    logger.debug(f"[Pipeline] 退出中间件: {middleware.__class__.__name__}")
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
