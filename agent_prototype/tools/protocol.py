"""基础设施层 (Infrastructure Layer) - 工具调用协议契约

职责：
1. 规定物理工具底层标准，定义 Tool 基类、参数类型校验规则与 Schema 声明协议。
2. 提供工具声明到 OpenAI 兼容的 JSON Schema 参数转换机制。

不负责：
1. 工具的实际拦截拦截及运行管道调度。
2. 工具收集器（ToolRegistry）的构建管理。

数据流向：
- 输入：具体的工具方法声明。
- 输出：标准化的 Tool 契约模型与 Schema。
- 上游来源：内置或自定义工具。
- 下游流向：被 agent_prototype/tools/registry.py 及 Application 层解析使用。
"""

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
