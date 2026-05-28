"""执行运行时类型定义。

职责：定义工具调用引擎的数据载体。
"""

from dataclasses import dataclass

from agent_prototype.core.types import AgentEvent
from agent_prototype.core.types import ChatMessage


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
