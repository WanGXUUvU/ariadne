"""执行运行时类型定义。

职责：
- 定义运行态状态快照与结构化事件。
- 定义工具调用阶段的中间结算载体。
"""

from typing import Literal, Optional
from pydantic import BaseModel, Field

from agent_prototype.core.types import ChatMessage
from agent_prototype.tools.result_types import ToolResult


class AgentState(BaseModel):
    """某个 session 的最新状态快照。"""

    messages: list[ChatMessage] = Field(default_factory=list)
    step: int = 0
    agent_name: Optional[str] = None


class AgentEvent(BaseModel):
    """一次 run 中的结构化事件。"""

    index: int
    type: Literal[
        "assistant_tool_call",
        "tool_result",
        "tool_error",
        "final_answer",
        "approval_required",
        "approval_result",
        "thinking",
        "tool_progress",
    ]
    content: Optional[str] = None
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_result: Optional[ToolResult] = None


class ToolTurnResult(BaseModel):
    """一次工具批次执行结束后的统一账单。"""

    events: list[AgentEvent] = Field(default_factory=list)
    tool_messages: list[ChatMessage] = Field(default_factory=list)
    next_event_index: int
    paused_for_approval: bool = False

