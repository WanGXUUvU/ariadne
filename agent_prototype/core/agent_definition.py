from pydantic import BaseModel, Field
from typing import Optional

class AgentDefinition(BaseModel):  # Agent 产品层定义
    id: str = Field(default="default")
    name: str = Field(default="Default Agent")
    system_prompt: str = Field(default="你是一个助手")
    description: Optional[str] = None
    tool_names: Optional[list[str]] = None  # 只存工具名；None 表示默认不限制

DEFAULT_AGENT_DEFINITION = AgentDefinition()  # 默认 skill 不限制工具，交给 registry 暴露全部
