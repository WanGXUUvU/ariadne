from typing import Protocol,Iterator,AsyncIterator
from agent_prototype.model.types.model_types import ModelRequest, ModelResponse, ModelStreamEvent

class ModelAdapter(Protocol):
    def generate(self,request:ModelRequest)->ModelResponse:
        """输入统一请求，输出统一响应"""
        ...
    def stream_generate(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:#表示这是一个可以逐步迭代的对象
        """输入统一请求，逐个 yield delta token 字符串"""
        ...
    
    async def async_stream_generate(self,request:ModelRequest)->AsyncIterator[ModelStreamEvent]:
        """用 async for 循环消费——每次迭代都是一个 await 点，Python 可以在这里检查"客户端是否断开"。"""
        ...