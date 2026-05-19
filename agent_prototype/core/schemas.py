"""项目核心数据模型。

这里定义的是 Pydantic schema，不是数据库 ORM：
- 请求体长什么样
- 响应体长什么样
- 运行时 state / event 长什么样

FastAPI 会基于这些模型做参数校验、类型转换和响应序列化。
"""

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 工具调用 — Tool Call
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
    """统一的工具执行结果。

    `metadata` 用 `default_factory=dict`，表示每次创建对象时都生成一个新字典，
    避免多个实例共享同一个可变默认值。
    """

    ok: bool
    content: Optional[str] = None
    error: Optional[ToolError] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolCallSummary(BaseModel):
    """单次工具调用的详情（持久化读取用）。"""

    id: int
    tool_name: str
    tool_call_id: Optional[str] = None
    status: str
    input_json: Optional[str] = None
    result_json: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 运行时消息 & 状态 — Runtime Message & State
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ChatMessage(BaseModel):
    """运行时消息对象，既用于上下文，也用于持久化 session state。"""

    role: Literal["system", "user", "assistant", "tool"]
    content: Optional[str] = None
    tool_calls: Optional[list[ToolCall]] = None
    tool_call_id: Optional[str] = None


class AgentState(BaseModel):
    """某个 session 的最新状态快照。"""

    messages: list[ChatMessage] = Field(default_factory=list)
    step: int = 0
    agent_name: Optional[str] = None


class AgentEvent(BaseModel):
    """一次 run 中的结构化事件。"""

    index: int
    type: Literal["assistant_tool_call", "tool_result", "tool_error", "final_answer","approval_required","approval_result"]
    content: Optional[str] = None
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_result: Optional[ToolResult] = None


class StreamFrame(BaseModel):
    """一条 SSE 推送帧的结构。

    type 取值：
    - start      : 运行开始，包含 session_id / run_id / agent_name / skill_name
    - agent_event: 一个语义事件（工具调用 / 工具结果 / 工具错误）
    - delta      : 最终回答阶段的 token 级增量内容
    - end        : 运行完成，包含完整 reply / state / metadata
    - error      : 运行失败，包含错误码和错误信息
    """

    type: Literal["start", "agent_event", "delta", "end", "error"]
    data: dict[str, Any]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Run 请求 & 响应 — Run I/O
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class AgentInput(BaseModel):
    """`/run` 请求体。"""

    agent_name: Optional[str] = None
    session_id: str = Field(min_length=1)
    user_input: str = Field(min_length=1)
    skill_name: Optional[str] = None  # 显式指定本轮要加载的 skill；不传时只给摘要目录


class RunMetadata(BaseModel):
    """一次 /run 的轻量元信息。"""  # 这个模型专门承载前端/CLI/测试最常读的运行标识信息

    session_id: str
    run_id: str = ""
    agent_name: Optional[str] = None
    skill_name: Optional[str] = None


class AgentOutput(BaseModel):
    """`/run` 响应体。"""

    reply: str
    state: AgentState
    events: list[AgentEvent]
    metadata: RunMetadata


class FinalizeRunInput(BaseModel):
    """内部用，run 完成时写库。"""

    user_input: str
    partial_reply: str
    agent_name: Optional[str] = None
    skill_name: Optional[str] = None


class RunDetailResponse(BaseModel):
    """GET /sessions/{id}/runs/{run_id} 的响应体。"""

    run_id: str
    session_id: str
    run_status: str
    user_input: str
    reply: str
    agent_name: Optional[str] = None
    skill_name: Optional[str] = None
    created_at: datetime
    tool_calls: list[ToolCallSummary]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Session 管理 — Session
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CreateSessionInput(BaseModel):
    """/session 创建请求体"""

    session_name: Optional[str] = Field(default=None, min_length=1)


class RenameSessionInput(BaseModel):
    """session 重命名请求体。"""

    session_name: str  # 新的会话名称


class ResetInput(BaseModel):
    """`/reset` 请求体。"""

    session_id: str = Field(min_length=1)


class SessionSummary(BaseModel):
    """session 列表页用的摘要信息。"""

    session_id: str
    session_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    last_agent_name: Optional[str] = None
    last_skill_name: Optional[str] = None
    message_count: int = 0
    last_reply_preview: Optional[str] = None
    permission_profile: str = "conservative"


class SessionDetail(SessionSummary):
    """session 详情，继承摘要信息并补上完整 state。"""

    state: AgentState


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Trace 回放 — Trace
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TraceRunSummary(BaseModel):
    """单次 run 的回放数据。"""

    run_id: str
    session_id: str
    agent_name: Optional[str] = None
    skill_name: Optional[str] = None
    user_input: str
    reply: str
    event_count: int
    created_at: datetime
    finished_at: datetime
    events: list[AgentEvent]


class TraceResponse(BaseModel):
    """`/sessions/{session_id}/trace` 的响应体。"""

    session_id: str
    runs: list[TraceRunSummary]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 上下文压缩 — Compact
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CompactInput(BaseModel):
    """/compact 请求体"""

    session_id: str = Field(min_length=1)
    trigger_threshold: int = Field(default=12, ge=1)  # 触发 compact 的消息阈值，默认 12，最小 1
    keep_recent_count: int = Field(default=2, ge=1)   # 压缩后保留最近几条原始消息，默认 2，最小 1


class CompactOutput(BaseModel):
    """/compact 响应体"""

    state: AgentState
    did_compact: bool
    removed_count: int = 0  # 一共折叠了多少条旧消息


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Skill — Skill
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SkillSummary(BaseModel):
    """skill 列表使用的轻量元数据"""

    name: str
    description: Optional[str] = None  # skill 摘要
    path: str                           # 裁剪后的安全路径
    enabled: bool = True
    error: Optional[str] = None         # skill 损坏时返回的错误信息


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 统一错误响应 — Error
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ApiError(BaseModel):
    """统一的业务错误内容。"""  # 这个模型只负责描述"错误本身长什么样"

    code: str    # 错误代码，给前端和测试一个稳定的机器可读标识
    message: str  # 错误信息，给用户界面直接展示的可读文本


class ErrorResponse(BaseModel):
    """统一的错误响应体。"""  # 这个模型表示 HTTP 错误返回时，整个 JSON 的外层结构

    error: ApiError  # 把具体错误信息统一收进 error 对象里，避免继续散在顶层


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 权限配置 — Permission  (TASK-042)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SandboxMode(str,Enum):
    READ_ONLY="read-only"
    WORKSPACE_WRITE="workspace-write"
    DANGER_FULL_ACCESS="danger-full-access"

class ApprovalPolicy(str,Enum):
    UNTRUSTED = "untrusted"   # 所有工具都要问
    ON_REQUEST = "on-request" # 危险操作才问
    NEVER = "never"           # 全放行

class PermissionProfile(BaseModel):
    name:str
    sandbox_mode:SandboxMode
    approval_policy:ApprovalPolicy
    workspace_path: Optional[str] = None

class RiskLevel(str, Enum):
    SAFE   = "safe"    # 只读，永远不需要审批
    WRITE  = "write"   # 写操作，视策略决定
    DANGER = "danger"  # 高危，除非 never 否则都要审批