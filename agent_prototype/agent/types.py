"""
[智能体定义层 - 类型定义]

Agent 定义相关的类型：AgentDefinition 及其预设常量。
原先在 core/types.py，现归位至本模块。
"""

from typing import Optional

from pydantic import BaseModel, Field


class AgentDefinition(BaseModel):
    """描述一个智能体（Agent）的"人设和超能力"配置定义。"""

    id: str = Field(default="default")
    name: str = Field(default="Default Agent")
    system_prompt: str = Field(default="你是一个助手")
    description: Optional[str] = None
    tool_names: Optional[list[str]] = None
    is_builtin: bool = False


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

__all__ = [
    "AgentDefinition",
    "DEFAULT_AGENT_DEFINITION",
    "ASSISTANT_AGENT_DEFINITION",
]
