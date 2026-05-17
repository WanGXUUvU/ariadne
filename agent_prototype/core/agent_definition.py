from pydantic import BaseModel, Field
from typing import Optional

class AgentDefinition(BaseModel):  # Agent 产品层定义
    id: str = Field(default="default")
    name: str = Field(default="Default Agent")
    system_prompt: str = Field(default="你是一个助手")
    description: Optional[str] = None
    tool_names: Optional[list[str]] = None  # 只存工具名；None 表示默认不限制

DEFAULT_AGENT_DEFINITION = AgentDefinition()  # 默认 skill 不限制工具，交给 registry 暴露全部
ASSISTANT_AGENT_DEFINITION= AgentDefinition(
    id="assistant",
    name= "Chat Assistant",
    system_prompt="你是一个友好、简洁、诚实的通用助理。回答时直接切入要点，不确定的事情如实说明，不要编造信息。",
    description="帮助用户完成日常任务",
    tool_names=["web_search"],
)