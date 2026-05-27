from dataclasses import dataclass
from typing import Any, Callable

from agent_prototype.model.types.domain import RiskLevel


# ── 工具定义 ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ToolDefinition:
    """单个工具的描述。frozen=True 确保定义不可变，避免运行中被改坏。"""

    name: str
    schema: dict
    handler: Callable[..., Any]
    risk_level: RiskLevel = RiskLevel.SAFE
