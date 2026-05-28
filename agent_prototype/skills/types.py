"""
[九层模型 - L4 Skill 层]

Skill 领域类型。

SkillSummary 原先寄生在 api/dto/schemas.py 中，导致 L2/L6/L4 自身均向上依赖 API 层。
归位到 skills/types 后所有上层只需 import 同层或低层模块即可。
"""

from typing import Optional
from pydantic import BaseModel


class SkillSummary(BaseModel):
    """skill 列表使用的轻量元数据。"""

    name: str
    description: Optional[str] = None
    path: str
    enabled: bool = True
    error: Optional[str] = None
