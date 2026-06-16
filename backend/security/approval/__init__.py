"""审批子模块包。

统一导出审批判定函数，使得调用方可以：
    from backend.security.approval import needs_approval
"""

from backend.security.approval.checker import needs_approval

__all__ = [
    "needs_approval",
]
