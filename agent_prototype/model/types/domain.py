"""
[九层模型 - L1 领域类型层 (Model Domain Layer)]

核心模型协议类型定义。

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
    """模型返回的 function calling 结构中的函数部分。
    
    大白话解释：
    这是大模型发出的“函数调用具体内容数据模型”。
    它包含大模型想要调用的具体函数名（name），以及 AI 生成的想喂给函数的参数（arguments，通常是一个 JSON 字符串）。
    """

    name: str
    arguments: str


class ToolCall(BaseModel):
    """一次工具调用请求。
    
    大白话解释：
    这是大模型发出的“单次工具调用订单数据模型”。
    它记录了这笔调用的唯一身份订单 ID（id），它的调用类型（默认为 "function"），以及上面所说的具体函数调用内容。
    """

    id: str
    type: Literal["function"] = "function"
    function: ToolCallFunction


class ToolError(BaseModel):
    """工具失败时返回给上层的结构化错误。
    
    大白话解释：
    这是工具执行失败时的“结构化病历单”。
    当工具跑崩了或者出错了，它不会随地吐痰，而是很优雅地开出这张单子，写清楚：错误码是什么（code，比如 SANDBOX_VIOLATION）、调哪个工具错的（tool_name），以及具体的报错大白话原因（message）。
    """

    ok: bool = False
    code: str
    tool_name: str
    message: str


class ToolResult(BaseModel):
    """统一的工具执行结果。
    
    大白话解释：
    这是统一的“工具执行结果收据包”。
    所有的工具在执行完后，不管成功还是失败，都要把成果塞进这个结果收据包里。包里包含：有没有成功（ok）、如果成功了拿回来的正文数据（content）、如果失败了的结构化错误单（error），以及可以装任何调试元数据的百宝袋（metadata）。
    """

    ok: bool
    content: Optional[str] = None
    error: Optional[ToolError] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 对话消息 — Chat Message
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ChatMessage(BaseModel):
    """运行时消息对象，既用于上下文，也用于持久化 session state。
    
    大白话解释：
    这是“单条聊天消息通用模型”。
    就像微信或者 QQ 里的单条气泡消息。它记下了：这条消息是谁发的（role，可以是系统 system、用户 user、助手 assistant，或者是代表工具反馈的 tool）；消息文本内容是什么（content）；如果 AI 发出消息的同时想调工具，这里面还会带上工具订单列表（tool_calls）；如果是工具回传的结果消息，这里面还会标上对应是给哪个订单（tool_call_id）的回复。
    """

    role: Literal["system", "user", "assistant", "tool"]
    content: Optional[str] = None
    tool_calls: Optional[list[ToolCall]] = None
    tool_call_id: Optional[str] = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 工具风险等级 — Risk Level
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class RiskLevel(str, Enum):
    """工具风险等级。
    
    大白话解释：
    这是给工具贴的“危险指数标签”。
    - SAFE: 绝对安全（比如纯读操作、Echo测试），可以绿灯直行，不需要人类审批。
    - WRITE: 有写入操作（比如往磁盘写文件），稍微有点敏感，会根据用户的安全策略决定要不要安检拦截。
    - DANGER: 高度危险（比如网络爬虫或者修改系统配置），除非安全策略是“极度放任”，否则必须拦截并呈交人类审批。
    """
    SAFE   = "safe"    # 只读，永远不需要审批
    WRITE  = "write"   # 写操作，视策略决定
    DANGER = "danger"  # 高危，除非 never 否则都要审批
