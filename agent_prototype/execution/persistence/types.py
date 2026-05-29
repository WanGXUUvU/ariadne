"""
[L8 执行层 - 持久化子模块类型定义]

执行层数据载体：RunContext + Run I/O 类型。
原先 AgentInput/AgentOutput/FinalizeRunInput/RunMetadata 在 core/types.py，现归位至本模块。
"""

from dataclasses import dataclass
from typing import Any, Optional

from pydantic import BaseModel, Field

from agent_prototype.agent.types import AgentDefinition
from agent_prototype.core.adapters.chat_completions import ChatCompletionsAdapter
from agent_prototype.execution.runtime.types import AgentState
from agent_prototype.security.policy.types import ApprovalPolicy


@dataclass
class RunContext:
    """智能体单次运行所需的所有背景物料。"""

    state: AgentState
    definition: AgentDefinition
    adapter: ChatCompletionsAdapter
    approval_policy: ApprovalPolicy
    effective_agent_name: str
    workspace_path: str
    session_type: str


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Run I/O
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class AgentInput(BaseModel):
    """`/run` 请求体。"""

    agent_name: Optional[str] = None
    session_id: str = Field(min_length=1)
    user_input: str = Field(min_length=1)
    skill_name: Optional[str] = None


class RunMetadata(BaseModel):
    """一次 /run 的轻量元信息。"""

    session_id: str
    run_id: str = ""
    agent_name: Optional[str] = None
    skill_name: Optional[str] = None


class AgentOutput(BaseModel):
    """`/run` 响应体。"""

    reply: str
    state: AgentState
    events: list
    metadata: RunMetadata
    usage: Optional[Any] = None


class FinalizeRunInput(BaseModel):
    """内部用，run 完成时写库。"""

    user_input: str
    partial_reply: str
    agent_name: Optional[str] = None
    skill_name: Optional[str] = None
