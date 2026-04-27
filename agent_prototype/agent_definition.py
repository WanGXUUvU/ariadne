from pydantic import BaseModel,Field
from typing import Optional
class AgentDefinition(BaseModel): #Agent产品层定义
    id:str=Field(default="default") 
    name:str =Field(default="Default Agent")
    system_prompt:str=Field(default="你是一个助手")
    description:Optional[str]=None
    tool_names:list[str]=Field(default_factory=list)#只存工具名

DEFAULT_AGENT_DEFINITION = AgentDefinition()  # 系统启动时的兜底定义
