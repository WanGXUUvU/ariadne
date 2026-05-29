"""
[L3 工具层 - 类型定义]

工具底层标准：Tool 基类、RiskLevel、参数类型校验规则与 Schema 声明协议。
原先 RiskLevel 在 core/types.py，现归位至本模块。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable


class RiskLevel(str, Enum):
    """工具风险等级。

    - SAFE: 绝对安全（比如纯读操作、Echo测试），可以绿灯直行，不需要人类审批。
    - WRITE: 有写入操作（比如往磁盘写文件），稍微有点敏感，会根据用户的安全策略决定要不要安检拦截。
    - DANGER: 高度危险（比如网络爬虫或者修改系统配置），除非安全策略是"极度放任"，否则必须拦截并呈交人类审批。
    """

    SAFE = "safe"
    WRITE = "write"
    DANGER = "danger"


# ── 工具定义 ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ToolDefinition:
    """单个工具的描述。frozen=True 确保定义不可变，避免运行中被改坏。"""

    name: str
    schema: dict
    handler: Callable[..., Any]
    risk_level: RiskLevel = RiskLevel.SAFE
