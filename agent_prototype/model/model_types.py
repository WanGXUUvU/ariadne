from typing import Any,Literal,Optional

from pydantic import BaseModel,Field

from ..core.schemas import ChatMessage,ToolCall

class ModelConfig(BaseModel):
    """一次模型调用配置"""

    model:Optional[str]=None
    temperature:Optional[float]=None #采样温度
    top_p:Optional[float]=None
    max_output_tokens:Optional[int]=None
    stream:bool=False
    tool_choice:Optional[Any]=None #工具选择策略
    previous_response_id:Optional[str]=None
    conversation:Optional[Any]=None
    provider_options:dict[str,Any]=Field(default_factory=dict)

class ModelRequest(BaseModel):
    """统一的模型请求对象"""

    messages:list[ChatMessage]=Field(default_factory=list)
    tools:list[dict[str,Any]]=Field(default_factory=list) #给模型看的schema
    config:ModelConfig #本次调用的模型的配置
    metadata:dict[str,Any]=Field(default_factory=dict) #业务元数据，方便trace和调试

class ModelUsage(BaseModel):
    """统一的 token 使用统计"""

    input_tokens:Optional[int]=None
    output_tokens:Optional[int]=None
    total_tokens:Optional[int]=None
    details:dict[str,Any]=Field(default_factory=dict) #厂商额外的usage信息

class ModelError(BaseModel):
    """统一的模型错误结构。"""

    code:str #错误码
    message:str #错误信息
    provider:Optional[str]=None #出错的厂商
    details:dict[str,Any]=Field(default_factory=dict)

class ModelResponse(BaseModel):
    """统一的模型相应对象"""

    assistant_message:ChatMessage
    id:Optional[str]=None #厂商响应id
    model:Optional[str]=None #返回的模型名字
    status:Literal["completed","incomplete","failed"]="completed"
    finish_reason:Optional[str]=None #结束原因
    usage:Optional[ModelUsage]=None
    error:Optional[ModelError]=None
    raw_response:dict[str,Any]=Field(default_factory=dict)
    provider_meta:dict[str,Any]=Field(default_factory=dict)

    @property
    def content(self)->Optional[str]:
        """上层常用正文快捷入口"""
        return self.assistant_message.content
    
    @property
    def tool_calls(self)->list[ToolCall]:

        return self.assistant_message.tool_calls or []
    
class ModelStreamEvent(BaseModel):
    """streaming 统一事件对象"""

    type: str  # 事件类型，先保持通用
    response_id: Optional[str] = None  # 事件所属 response id
    content_delta: Optional[str] = None  # 增量文本
    tool_call_id: Optional[str] = None  # 工具调用 id
    tool_name: Optional[str] = None  # 工具名
    finish_reason: Optional[str] = None  # 流结束原因
    usage: Optional[ModelUsage] = None  # 结束时的 usage
    error: Optional[ModelError] = None  # 流式错误信息
    raw_event: dict[str, Any] = Field(default_factory=dict)  # 原始事件，便于调试
