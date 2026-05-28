"""接口层 DTO 模型 (Data Transfer Objects)。

面向 HTTP API 的请求/响应模型。本模块只承载"HTTP I/O 形状"：
- 请求体（Input）：HTTP 入参的反序列化形状
- 响应体（Output / Summary / Detail / Response）：HTTP 出参的序列化形状
- 错误体（ApiError / ErrorResponse）：统一错误返回的 JSON 结构

核心领域类型已归位至各自所在低层模块，路由层应直接从低层导入。
本文件只保留 HTTP 专属的 DTO 定义。
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

from agent_prototype.core.types import AgentEvent, AgentState, SessionSummary


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 工具调用摘要 — Tool Call Summary
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

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
# Session 详情 — Session Detail (HTTP 专属扩展)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class SessionDetail(SessionSummary):
    """session 详情，继承摘要信息并补上完整 state。"""

    state: AgentState
    model_id: Optional[str] = None
    model_provider_id: Optional[int] = None
    thinking_enabled: bool = False
    thinking_effort: str = "medium"

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
# 设置 — Settings (HTTP 专属输入形状)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CreateProviderInput(BaseModel):
    name: str
    base_url: str
    api_key: str

class PatchProviderInput(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    is_default: Optional[bool] = None

class PatchModelInput(BaseModel):
    enabled: Optional[bool] = None
    display_name: Optional[str] = None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 工作区管理 — Workspace
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class WorkspaceSummary(BaseModel):
    """已注册工作区的摘要响应体。"""

    id: int
    name: str
    path: str
    created_at: datetime

    class Config:
        from_attributes = True  # 允许从 SQLAlchemy ORM 物理实体直接初始化
