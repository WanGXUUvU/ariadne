from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from agent_prototype.interface.dto.schemas import CreateSessionInput, SessionDetail, SessionSummary, RenameSessionInput
from agent_prototype.application.services.session_service import SessionService
from agent_prototype.infrastructure.database.db import get_db
from agent_prototype.infrastructure.database.repositories.session_store import SqliteSessionStore
from agent_prototype.interface.api.routes.common import error_response

router = APIRouter()


@router.post("/sessions", response_model=SessionSummary)
def create_session_api(payload: CreateSessionInput, db: Session = Depends(get_db)) -> SessionSummary:
    service = SessionService(db)
    return service.create_session(payload)


@router.delete("/sessions/{session_id}")
def delete_session_api(session_id: str, db: Session = Depends(get_db)) -> dict[str, bool]:
    try:
        service = SessionService(db)
        return service.delete_session(session_id)
    except ValueError as exc:
        return error_response(status.HTTP_400_BAD_REQUEST, "bad_request", str(exc))


@router.get("/sessions", response_model=list[SessionSummary])
def list_sessions_api(db: Session = Depends(get_db)) -> list[SessionSummary]:
    store = SqliteSessionStore(db)
    records = store.list_sessions()
    return [
        SessionSummary(
            session_id=record.session_id,
            session_name=record.session_name,
            created_at=record.created_at,
            updated_at=record.updated_at,
            last_agent_name=record.last_agent_name,
            last_skill_name=record.last_skill_name,
            message_count=record.message_count,
            last_reply_preview=record.last_reply_preview,
            permission_profile=record.permission_profile,
            context_tokens=record.context_tokens,
            workspace_path=record.workspace_path,
            workspace_name=record.workspace_name,
            session_type=record.session_type,
        )
        for record in records
    ]


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def read_session_api(session_id: str, db: Session = Depends(get_db)) -> SessionDetail:
    store = SqliteSessionStore(db)
    record = store.read_session_record(session_id)
    if record is None:
        return error_response(status.HTTP_404_NOT_FOUND, "session_not_found", "Session not found")
        
    state = store.read_session_state(session_id)
    if state is None:
        return error_response(status.HTTP_404_NOT_FOUND, "session_not_found", "Session not found")
        
    return SessionDetail(
        session_id=record.session_id,
        session_name=record.session_name,
        created_at=record.created_at,
        updated_at=record.updated_at,
        last_agent_name=record.last_agent_name,
        last_reply_preview=record.last_reply_preview,
        last_skill_name=record.last_skill_name,
        message_count=record.message_count,
        state=state,
        permission_profile=record.permission_profile,
        model_id=record.model_id,
        model_provider_id=record.model_provider_id,
        thinking_enabled=bool(record.thinking_enabled),
        thinking_effort=record.thinking_effort or "medium",
        workspace_path=record.workspace_path,
        workspace_name=record.workspace_name,
        session_type=record.session_type,
    )  


@router.patch("/sessions/{session_id}")
def rename_session_api(session_id: str, payload: RenameSessionInput, db: Session = Depends(get_db)) -> dict[str, bool]:
    """🌟 拒绝控制器层越权写 DB，完全收归业务服务类实例化调用"""
    try:
        service = SessionService(db)
        return service.update_session(session_id, payload)
    except ValueError as exc:
        return error_response(status.HTTP_400_BAD_REQUEST, "bad_request", str(exc))