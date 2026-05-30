from dataclasses import dataclass,field
from typing import Literal,Optional

from agent_prototype.core.types import ChatMessage, ToolCall
from agent_prototype.execution.runtime.types import AgentEvent


ToolBatchStatus = Literal[
    "running",
    "waiting_approval",
    "completed",
]

ToolBatchItemStatus = Literal[
    "ready",              # 无需审批，尚未开始执行
    "running",            # 正在执行
    "approval_pending",   # 等待人工审批
    "approved",           # 用户已批准，尚未真正执行
    "rejected",           # 用户拒绝，视为终态
    "completed",          # 工具执行成功完成
    "failed",             # 工具执行失败，视为终态
]

@dataclass
class ToolBatchItem:
    """一轮 assistant tool_calls 里的单个工具调用条目。"""

    tool_call_id: str
    tool_name: str
    arguments: str

    requires_approval: bool
    status: ToolBatchItemStatus

    approval_id: Optional[str] = None
    result_message: Optional[ChatMessage] = None
    result_event: Optional[AgentEvent] = None

    def is_terminal(self) -> bool:
        """终态 = 已完成 / 已拒绝 / 已失败。"""
        return self.status in {"completed", "rejected", "failed"}

@dataclass
class ToolBatch:
    """同一轮 assistant 返回的一整批 tool_calls。"""

    run_id: str
    batch_id: str
    items: list[ToolBatchItem] = field(default_factory=list)
    status: ToolBatchStatus = "running"

    def all_terminal(self) -> bool:
        """整批是否全部进入终态。"""
        return all(item.is_terminal() for item in self.items)

    def has_pending_approval(self) -> bool:
        """是否还存在等待用户处理的审批项。"""
        return any(item.status == "approval_pending" for item in self.items)

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
                status="approval_pending" if need_approval else "ready",
            )
        )

    batch = ToolBatch(
        run_id=run_id,
        batch_id=batch_id,
        items=items,
        status="waiting_approval" if any(i.requires_approval for i in items) else "running",
    )
    return batch

