from dataclasses import dataclass, field
from typing import Optional

from agent_prototype.core.types import ChatMessage, ToolCall
from agent_prototype.execution.runtime.types import RunEvent


@dataclass
class ToolBatchItem:
    """一轮 assistant tool_calls 里的单个工具调用条目。"""

    tool_call_id: str
    tool_name: str
    arguments: str

    requires_approval: bool

    approval_id: Optional[str] = None
    result_message: Optional[ChatMessage] = None
    result_event: Optional[RunEvent] = None


@dataclass
class ToolBatch:
    """同一轮 assistant 返回的一整批 tool_calls。"""

    run_id: str
    batch_id: str
    items: list[ToolBatchItem] = field(default_factory=list)

    def find_item(self, tool_call_id: str) -> ToolBatchItem:
        """按 tool_call_id 找到对应条目，找不到就抛错。"""
        for item in self.items:
            if item.tool_call_id == tool_call_id:
                return item
        raise KeyError(f"Tool batch item not found: {tool_call_id}")


def build_tool_batch(
    run_id: str,
    batch_id: str,
    tool_calls: list[ToolCall],
    approval_checker,
) -> ToolBatch:
    """把一轮 tool_calls 预检并组装成 ToolBatch。

    approval_checker:
        一个可调用对象，签名形如 approval_checker(tool_name: str) -> bool
        返回 True 表示该工具需要审批。
    """
    items: list[ToolBatchItem] = []

    for tool_call in tool_calls:
        need_approval = approval_checker(tool_call.function.name)
        items.append(
            ToolBatchItem(
                tool_call_id=tool_call.id,
                tool_name=tool_call.function.name,
                arguments=tool_call.function.arguments,
                requires_approval=need_approval,
            )
        )

    batch = ToolBatch(
        run_id=run_id,
        batch_id=batch_id,
        items=items,
    )
    return batch
