"""审批判定逻辑。

职责：根据审批策略与风险等级，判定是否需要人工审批。
属于 security/approval 审批闭环的一部分：checker(判定) → middleware(拦截) → store(持久化)。
"""

from agent_prototype.core.types import RiskLevel
from agent_prototype.security.policy import ApprovalPolicy


def needs_approval(policy: ApprovalPolicy, risk: RiskLevel) -> bool:
    """根据审批策略和风险等级判断是否需要审批。"""
    if policy == ApprovalPolicy.NEVER:
        return False
    if policy == ApprovalPolicy.UNTRUSTED:
        return risk != RiskLevel.SAFE
    if policy == ApprovalPolicy.ON_REQUEST:
        return risk == RiskLevel.DANGER
    return False
