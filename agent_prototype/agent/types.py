"""
[智能体定义层 - 类型 re-export]

文件职责：
- 向后兼容 re-export AgentDefinition 及其预设常量。
- 实际定义已归位至 core/types.py，以消除 L6/L7/L8 对 L10 的反向依赖。

上游依赖：L1 core.types。
下游依赖：L8 执行层、L6 上下文层、L10 API 接口层 DTO。
"""

from agent_prototype.core.types import (
    AgentDefinition,
    ASSISTANT_AGENT_DEFINITION,
    DEFAULT_AGENT_DEFINITION,
)

__all__ = [
    "AgentDefinition",
    "ASSISTANT_AGENT_DEFINITION",
    "DEFAULT_AGENT_DEFINITION",
]
