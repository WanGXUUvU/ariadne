"""
[记忆层 - Summary 子模块类型定义]

上下文压缩相关的领域类型。
原先在 core/types.py，现归位至本模块。
"""

from typing import Optional

from pydantic import BaseModel, Field

from agent_prototype.execution.runtime.types import AgentState


class CompactInput(BaseModel):
    """压缩请求参数（领域语义，非 HTTP 形状）。"""

    session_id: str = Field(min_length=1)
    trigger_threshold: int = Field(default=12, ge=1)
    keep_recent_count: int = Field(default=2, ge=1)
    force: bool = Field(default=False)


class CompactOutput(BaseModel):
    """压缩结果（领域语义，非 HTTP 形状）。"""

    state: AgentState
    did_compact: bool
    removed_count: int = 0
    compact_tokens: Optional[int] = None
