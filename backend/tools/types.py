"""工具描述核心类型定义。

职责：
- 定义系统内工具注册规范：ToolDefinition 类。
- 提供工具安全拦截评估依赖的安全风险等级 Enum：RiskLevel。

上游：
- ToolRegistry

下游：
- 各内置工具的 build_definition 方法

不负责：
- 不提供工具的具体运行时执行逻辑。
- 不做具体模型的协议消息转换。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable


class RiskLevel(str, Enum):
    """工具安全风险等级。

    - SAFE: 绝对安全（只读或 Echo 测试），无须人类审批。
    - WRITE: 有写入操作，基于安全策略决定是否拦截审批。
    - DANGER: 高风险敏感操作，默认必须进行人类审批。
    """

    SAFE = "safe"
    WRITE = "write"
    DANGER = "danger"


# ── 工具定义 ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ToolDefinition:
    """单个工具的只读注册描述。"""

    name: str
    schema: dict
    handler: Callable[..., Any]
    risk_level: RiskLevel = RiskLevel.SAFE
