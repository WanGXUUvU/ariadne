"""执行运行时类型定义。

职责：
- 定义运行态状态快照与结构化事件。
- 定义工具调用阶段的中间结算载体。
"""

from dataclasses import dataclass
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
    ]
    content: Optional[str] = None
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_result: Optional[ToolResult] = None


@dataclass
class ToolTurnResult:
    """这是一个"一轮工具调用处理完后的结算账单（结果实体）"。
    当智能体把一轮里的所有工具全部调用完（或者中途因为需要审批而暂停）后，它会用这个账单把产生的事件、追加的消息、
    下一个事件的序号、以及是不是"因为要审批所以暂停了"等信息给汇总打包。
    """

    events: list[AgentEvent]
    tool_messages: list[ChatMessage]
    next_event_index: int
    paused_for_approval: bool = False
