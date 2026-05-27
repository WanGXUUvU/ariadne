"""核心模型协议类型定义。

本模块是 model 层的类型基础，仅包含 LLM 协议原语：
- 工具调用原语（ToolCall / ToolResult / ToolError）
- 对话消息（ChatMessage）
- 风险等级（RiskLevel）—— 作为工具的静态属性标记

安全策略类型（ApprovalPolicy / PermissionProfile / PROFILES）定义在 security/policy.py。
本模块绝不依赖任何上层模块。
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
# 工具风险等级 — Risk Level
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class RiskLevel(str, Enum):
    SAFE   = "safe"    # 只读，永远不需要审批
    WRITE  = "write"   # 写操作，视策略决定
    DANGER = "danger"  # 高危，除非 never 否则都要审批

