"""安全模块。

统一导出安全层核心类型，使得调用方可以：
    from agent_prototype.security import ApprovalPolicy, ToolCallContext
"""

from agent_prototype.security.policy import ApprovalPolicy, SandboxMode, PermissionProfile, PROFILES
from agent_prototype.security.types import ToolCallContext

__all__ = [
    "ApprovalPolicy",
    "SandboxMode",
    "PermissionProfile",
    "PROFILES",
    "ToolCallContext",
]
