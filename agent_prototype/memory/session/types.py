"""
[记忆层 - Session 子模块类型定义]

Session 管理相关的领域类型。
原先在 core/types.py，现归位至本模块。
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CreateSessionInput(BaseModel):
    """创建 session 的领域输入。"""

    session_name: Optional[str] = Field(default=None, min_length=1)
    workspace_path: Optional[str] = None
    workspace_name: Optional[str] = None
    session_type: Optional[str] = Field(default="coding")


class RenameSessionInput(BaseModel):
    """session 更新的领域输入。"""

    session_name: Optional[str] = None
    permission_profile: Optional[str] = None
    model_id: Optional[str] = None
    model_provider_id: Optional[int] = None
    thinking_enabled: Optional[bool] = None
    thinking_effort: Optional[str] = None
    workspace_path: Optional[str] = None
    workspace_name: Optional[str] = None


class ResetInput(BaseModel):
    """重置 session 的领域输入。"""

    session_id: str = Field(min_length=1)


class SessionSummary(BaseModel):
    """session 摘要信息（领域语义，非 HTTP 形状）。"""

    session_id: str
    session_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    last_agent_name: Optional[str] = None
    message_count: int = 0
    last_reply_preview: Optional[str] = None
    permission_profile: str = "conservative"
    context_tokens: Optional[int] = None
    workspace_path: Optional[str] = None
    workspace_name: Optional[str] = None
    session_type: Optional[str] = Field(default="coding")
    parent_session_id: Optional[str] = None
    fork_message_index: Optional[int] = None


class TruncateSessionInput(BaseModel):
    """截断 session 的领域输入结构体。"""
    message_index: int = Field(ge=0)

class ForkSessionInput(BaseModel):
    """派生分支会话的领域输入结构体。"""
    message_index: int = Field(ge=0)
    new_content: Optional[str] = None