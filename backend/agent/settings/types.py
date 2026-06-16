"""全局配置类型定义。

职责：
- 定义大模型厂商及模型配置的领域传输模型（DTO）。

上游：
- SettingsService
- Settings Store

下游：
- 无

不负责：
- 不做数据库物理表定义。
- 不包含业务逻辑。
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
