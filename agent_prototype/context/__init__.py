"""上下文模块。

统一导出上下文层核心类型与服务，使得调用方可以：
    from agent_prototype.context import AssembledContext, ContextAssembler
"""

from agent_prototype.context.types import AssembledContext
from agent_prototype.context.assembler import ContextAssembler
from agent_prototype.context.compaction import HistoryCompactor
from agent_prototype.context.skill_context import SkillContextService

__all__ = [
    "AssembledContext",
    "ContextAssembler",
    "HistoryCompactor",
    "SkillContextService",
]
