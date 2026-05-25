from typing import Optional

from pydantic import BaseModel, Field


# ── 领域模型 ──────────────────────────────────────────────────────────────────

class AgentDefinition(BaseModel):
    """Agent 产品层定义。"""

    id: str = Field(default="default")
    name: str = Field(default="Default Agent")
    system_prompt: str = Field(default="你是一个助手")
    description: Optional[str] = None
    tool_names: Optional[list[str]] = None  # None 表示不限制，暴露全部工具
    is_builtin: bool = False                # True 表示来自内置 .md 文件，不可删除


# ── 内置预设定义 ──────────────────────────────────────────────────────────────

DEFAULT_AGENT_DEFINITION = AgentDefinition()

ASSISTANT_AGENT_DEFINITION = AgentDefinition(
    id="assistant",
    name="Chat Assistant",
    system_prompt=(
        "你是一个友好、简洁、诚实的通用助理。"
        "回答时直接切入要点，不确定的事情如实说明，不要编造信息。"
    ),
    description="帮助用户完成日常任务",
    tool_names=["web_search"],
)
