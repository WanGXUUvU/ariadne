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
    """工具调用上下文对象
    
    大白话解释：
    这是一个“安检小推车（工具调用上下文）”。
    当 AI 想要调一个工具时，它会把这个工具的名字（tool_name）、想传的参数（tool_args）、这次调用的身份证号（tool_call_id）、属于哪个聊天会话（session_id）、以及这次运行的 ID（run_id）通通装在这辆小推车里。小推车还会拉上一个“百宝袋（extra）”，方便安检管道中的各个关卡（中间件）往里塞一些临时的共享小标签。
    """

    tool_name: str
    tool_args: str
    tool_call_id: str
    session_id: str
    run_id: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)
    """元数据字典，用于不同拦截器之间传递自定义状态或配置"""


class BaseMiddleware(ABC):
    """通用中间件基类（遵循标准的洋葱圈中间件规范）。
    
    大白话解释：
    这是一个“安检关卡模版（中间件基类）”。
    如果你想写一个新的安检过滤关卡（比如路径沙箱拦截、人工审批等），你的新关卡必须严格按照这个模版来做。它规定你必须要实现一个 `call` 动作，用来执行你这一关的检查。
    """

    @abstractmethod
    async def call(
        self,
        context: Any,
        next_call: Callable[[], Awaitable[Any]],
    ) -> Any:
        """
        大白话解释：
        这是每个安检关卡具体执行检查的动作。
        在这个函数里，你可以检查小推车里的数据。如果你觉得没问题，就必须调用一下 `next_call()` 放行，让小车开往下一关；如果你觉得不对劲，你可以直接抛出异常或者直接返回报错，把小推车拦在这里。

        需要拿到的东西：
        - context: 正在接受检查的“安检小推车”。
        - next_call (Callable): 指向下一关卡的放行通行证函数。
        """
        pass


class MiddlewarePipeline:
    """通用中间件管道执行器，负责把所有中间件像洋葱圈一样套起来执行。
    
    大白话解释：
    这个类是“洋葱安检传送带（中间件管道）”。
    它负责把各个安检关卡（中间件）按顺序排成一排。当你把“安检小推车”推上传送带时，这个执行器就会带着它像剥洋葱一样，层层深入每一个关卡做检查，最后把小车平安送到终点执行工具，然后再带着执行结果原路退出来。
    """

    def __init__(self, middlewares: list[BaseMiddleware]):
        """
        大白话解释：
        洋葱传送带初始化，把你需要部署的各个安检关卡排好队。

        需要拿到的东西：
        - middlewares (list[BaseMiddleware]): 你想要摆上安检传送带的中间件关卡列表。
        """
        self.middlewares = middlewares

    async def execute(
        self,
        context: Any,
        terminal_call: Callable[[], Awaitable[Any]],
    ) -> Any:
        """
        大白话解释：
        启动洋葱传送带，让安检小车开始接受层层安检。
        小车会被最外层的关卡开始检查，如果通过就深入到第二层、第三层……直到所有关卡都放行后，到达终点（terminal_call）执行真正的工具，最后把工具吐出来的结果层层传回。

        需要拿到的东西：
        - context (Any): 装满工具调用数据的“安检小推车”。
        - terminal_call (Callable): 传送带最深处终点站的执行函数（一般是真正去调用物理工具的函数）。

        会给出来的结果：
        - Any: 工具执行完后拿回来的结果数据。
        """
        current_call = terminal_call

        def make_next_call(
            middleware: BaseMiddleware,
            next_fn: Callable[[], Awaitable[Any]],
        ) -> Callable[[], Awaitable[Any]]:
            """
            大白话解释：
            制造一张让小车通往下一个关卡的“通行证（闭包回调函数）”。
            """
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
