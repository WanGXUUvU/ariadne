"""技能模块。

统一导出技能层核心类型与服务，使得调用方可以：
    from backend.skills import SkillSummary, SkillService
"""

from backend.skills.types import SkillSummary
from backend.skills.loader import list_skills
from backend.skills.service import SkillService

__all__ = [
    "SkillSummary",
    "list_skills",
    "SkillService",
]
