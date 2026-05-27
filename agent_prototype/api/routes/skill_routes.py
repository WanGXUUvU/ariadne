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