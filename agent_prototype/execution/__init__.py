"""执行模块。

统一导出执行层核心类型与服务，使得调用方可以：
    from agent_prototype.execution import RunContext, RunService
"""

from agent_prototype.execution.persistence.types import RunContext
from agent_prototype.execution.service import RunService

__all__ = [
    "RunContext",
    "RunService",
]
