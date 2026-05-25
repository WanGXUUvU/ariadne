"""核心领域类型定义。

本模块是整个项目最底层的类型基础：
- 工具调用原语（ToolCall / ToolResult / ToolError）
- 对话消息（ChatMessage）
- 权限与风险策略（RiskLevel / ApprovalPolicy / PermissionProfile）

其他层（infrastructure / application / interface）均可向上依赖本模块，
但本模块绝不依赖任何上层模块。
"""

from enum import Enum
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 工具调用原语 — Tool Call Primitives
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ToolCallFunction(BaseModel):
    """模型返回的 function calling 结构中的函数部分。"""

    name: str
    arguments: str


class ToolCall(BaseModel):
    """一次工具调用请求。"""

    id: str
    type: Literal["function"] = "function"
    function: ToolCallFunction


class ToolError(BaseModel):
    """工具失败时返回给上层的结构化错误。"""

    code: str
    tool_name: str
    message: str


class ToolResult(BaseModel):
    """统一的工具执行结果。"""

    ok: bool
    content: Optional[str] = None
    error: Optional[ToolError] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 对话消息 — Chat Message
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ChatMessage(BaseModel):
    """运行时消息对象，既用于上下文，也用于持久化 session state。"""

    role: Literal["system", "user", "assistant", "tool"]
    content: Optional[str] = None
    tool_calls: Optional[list[ToolCall]] = None
    tool_call_id: Optional[str] = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 权限与风险策略 — Permission & Risk
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class RiskLevel(str, Enum):
    SAFE   = "safe"    # 只读，永远不需要审批
    WRITE  = "write"   # 写操作，视策略决定
    DANGER = "danger"  # 高危，除非 never 否则都要审批


class SandboxMode(str, Enum):
    READ_ONLY          = "read-only"
    WORKSPACE_WRITE    = "workspace-write"
    DANGER_FULL_ACCESS = "danger-full-access"


class ApprovalPolicy(str, Enum):
    UNTRUSTED  = "untrusted"   # 所有工具都要问
    ON_REQUEST = "on-request"  # 危险操作才问
    NEVER      = "never"       # 全放行


class PermissionProfile(BaseModel):
    name: str
    sandbox_mode: SandboxMode
    approval_policy: ApprovalPolicy
    workspace_path: Optional[str] = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 内置权限档位 — Built-in Permission Profiles
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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

