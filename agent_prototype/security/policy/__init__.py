"""安全策略包。

统一导出所有策略类型与常量，使得调用方可以：
    from agent_prototype.security.policy import ApprovalPolicy, SandboxMode, ...

而无需知道具体在哪个子模块中定义。
"""

from agent_prototype.security.policy.types import (
    ApprovalPolicy,
    PermissionProfile,
    PROFILES,
    SandboxMode,
)

__all__ = [
    "ApprovalPolicy",
    "PermissionProfile",
    "PROFILES",
    "SandboxMode",
]
