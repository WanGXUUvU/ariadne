from typing import Any,Literal,Optional
from pydantic import BaseModel,Field

from ..core.schemas import ChatMessage

class ModelConfig(BaseModel):
    """一次模型调用配置"""

    model:str
    temperature:Optional[float]=None #采样温度
    top_p:Optional[float]=None
    max_output_token:Optional[int]=None
    stream:bool=False
    tool_choice:Optional[Any]=None #工具选择策略
    preivous_response_id:Optional[str]=None
    conversation:Optional[Any]=None
    provider_options:dict[str,Any]=Field(default_factory=dict)

class ModelRequest(BaseModel):
    """统一的模型请求对象"""

    message:list[ChatMessage]
    instructions:Optional[str]=None #系统级指令和普通消息分开
