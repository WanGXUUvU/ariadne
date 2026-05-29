"""
[智能体设置层 - 类型定义]

模型供应商与模型配置的领域类型。
原先在 core/types.py，现归位至本模块。
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ProviderOut(BaseModel):
    """供应商领域模型（含脱敏 API Key 提示）。"""

    id: int
    name: str
    base_url: str
    api_key_hint: Optional[str] = None
    is_default: bool
    created_at: datetime


class ModelOut(BaseModel):
    """模型领域模型。"""

    id: int
    provider_id: int
    model_id: str
    display_name: str
    enabled: bool
    supports_thinking: bool
    thinking_style: str
    effort_levels: list[str]
    context_length: Optional[int]
    supports_tools: bool
