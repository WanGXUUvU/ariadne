"""审批子模块包。

统一导出审批判定函数，使得调用方可以：
    from agent_prototype.security.approval import needs_approval
"""

from agent_prototype.security.approval.checker import needs_approval

__all__ = [
    "needs_approval",
]
