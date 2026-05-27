"""安全策略类型定义。

职责：定义 Session/Agent 级别的权限与审批策略，供 security 层内部及上层（api、execution）使用。
不依赖 model/ 层之外的任何其他层。
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel

from agent_prototype.model.types.domain import RiskLevel


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 沙箱模式 — Sandbox Mode
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SandboxMode(str, Enum):
    READ_ONLY          = "read-only"
    WORKSPACE_WRITE    = "workspace-write"
    DANGER_FULL_ACCESS = "danger-full-access"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 审批策略 — Approval Policy
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ApprovalPolicy(str, Enum):
    UNTRUSTED  = "untrusted"   # 所有工具都要问
    ON_REQUEST = "on-request"  # 危险操作才问
    NEVER      = "never"       # 全放行


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 权限档位 — Permission Profile
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PermissionProfile(BaseModel):
    name: str
    sandbox_mode: SandboxMode
    approval_policy: ApprovalPolicy
    workspace_path: Optional[str] = None


PROFILES: dict[str, PermissionProfile] = {
    "conservative": PermissionProfile(
        name="conservative",
        sandbox_mode=SandboxMode.READ_ONLY,
        approval_policy=ApprovalPolicy.UNTRUSTED,
    ),
    "standard": PermissionProfile(
        name="standard",
        sandbox_mode=SandboxMode.WORKSPACE_WRITE,
        approval_policy=ApprovalPolicy.ON_REQUEST,
    ),
    "full-auto": PermissionProfile(
        name="full-auto",
        sandbox_mode=SandboxMode.DANGER_FULL_ACCESS,
        approval_policy=ApprovalPolicy.NEVER,
    ),
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 审批判定辅助函数 — Approval Check Helper
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def needs_approval(policy: ApprovalPolicy, risk: RiskLevel) -> bool:
    """根据审批策略和风险等级判断是否需要审批。"""
    if policy == ApprovalPolicy.NEVER:
        return False
    if policy == ApprovalPolicy.UNTRUSTED:
        return risk != RiskLevel.SAFE
    if policy == ApprovalPolicy.ON_REQUEST:
        return risk == RiskLevel.DANGER
    return False
