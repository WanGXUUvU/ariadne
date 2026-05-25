from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from agent_prototype.interface.dto.schemas import CompactInput, CompactOutput
from agent_prototype.application.services.compact_service import CompactService
from agent_prototype.infrastructure.database.db import get_db
from agent_prototype.interface.api.routes.common import error_response

router = APIRouter()


@router.post("/compact", response_model=CompactOutput)
def compact_session_api(payload: CompactInput, db: Session = Depends(get_db)) -> CompactOutput:
    """输入：CompactInput 历史压缩参数、数据库会话。输出：CompactOutput 压缩结果。"""
    try:
        service = CompactService(db)
        return service.compact_session(payload)
    except ValueError as exc:
        return error_response(status.HTTP_400_BAD_REQUEST, "bad_request", str(exc))