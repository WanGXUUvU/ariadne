from pydantic import BaseModel, Field
from typing import List,Literal,Optional

# Pydantic 对象，你可以直接理解成：

# “带校验规则的 Python 数据对象”。

# 它不是普通的 dict，也不是普通的 class 随便装数据。
# 它的特点是：

# 创建时会自动校验字段
# 会自动把数据转换成合适的类型
# 能方便地转成 dict / JSON
# 常用在 FastAPI 里做请求和响应的数据结构

class ToolCallFunction(BaseModel):
    name:str
    arguments:str

class ToolCall(BaseModel):
    id:str
    type:Literal["function"]="function"
    function:ToolCallFunction

class ChatMessage(BaseModel):
    role:Literal["system","user","assistant","tool"]
    content:Optional[str]=None
    tool_calls:Optional[list[ToolCall]]=None
    tool_call_id:Optional[str]=None
#单词运行请求
class AgentInput(BaseModel):
    session_id:str=Field(min_length=1) #会话id，隔离会话
    user_input:str =Field(min_length=1)
#重置请求
class ResetInput(BaseModel):
    session_id:str=Field(min_length=1)

class AgentState(BaseModel):
    messages:List[ChatMessage]=Field(default_factory=list)
    step:int=0

class AgentEvent(BaseModel):
    type:Literal["assistant_tool_call","tool_result","final_answer"]
    content:Optional[str]=None
    tool_name:Optional[str]=None
    tool_call_id:Optional[str]=None

class AgentOutput(BaseModel):
    reply:str
    state:AgentState
    events: List[AgentEvent]
