from typing import Protocol
from .model_types import ModelRequest,ModelResponse

class ModelAdapter(Protocol):
    def generate(self,request:ModelRequest)->ModelResponse:
        """输入统一请求，输出统一响应"""
        ...