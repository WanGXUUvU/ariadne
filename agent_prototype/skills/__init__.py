"""技能模块。

统一导出技能层核心类型与服务，使得调用方可以：
    from agent_prototype.skills import SkillSummary, SkillService
"""

from agent_prototype.skills.types import SkillSummary
from agent_prototype.skills.loader import list_skills
from agent_prototype.skills.service import SkillService

__all__ = [
    "SkillSummary",
    "list_skills",
    "SkillService",
]
