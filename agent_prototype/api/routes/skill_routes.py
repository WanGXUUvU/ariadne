"""接口与适配层 (Interface Layer) - 技能管理路由控制器

职责：
1. 提供技能管理的路由控制器，支持技能的列出、上传、启用/禁用。
2. 进行技能上传的参数与包名验证。

不负责：
1. 技能 Python 模块的物理动态导入。
2. 技能在运行时执行上下文中的参数装配。

数据流向：
- 输入：HTTP 请求及技能动作参数。
- 输出：技能列表或启用状态 JSON 响应。
- 上游来源：前端。
- 下游流向：调用 agent_prototype/skills/service.py。
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from agent_prototype.api.dto.schemas import SkillSummary
from agent_prototype.skills.service import SkillService
from agent_prototype.infra.db.engine import get_db
from agent_prototype.api.routes.dependencies import error_response

router = APIRouter()


@router.get("/skills", response_model=list[SkillSummary])
def list_skills_api(db: Session = Depends(get_db)) -> list[SkillSummary]:
    service = SkillService(db)
    return service.list_skills()


@router.post("/skills/{skill_name}/disable", response_model=SkillSummary)
def disable_skill_api(skill_name: str, db: Session = Depends(get_db)) -> SkillSummary:
    try:
        service = SkillService(db)
        return service.disable_skill(skill_name)
    except ValueError as exc:
        return error_response(status.HTTP_400_BAD_REQUEST, "bad_request", str(exc))


@router.post("/skills/{skill_name}/enable", response_model=SkillSummary)
def enable_skill_api(skill_name: str, db: Session = Depends(get_db)) -> SkillSummary:
    try:
        service = SkillService(db)
        return service.enable_skill(skill_name)
    except ValueError as exc:
        return error_response(status.HTTP_400_BAD_REQUEST, "bad_request", str(exc))