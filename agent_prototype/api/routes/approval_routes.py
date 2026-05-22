from ...application.approval_service import reject_service, approve_service, get_approval_service
from ...application.resume_run_service import resume_run_service
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from ...storage.db import get_db
from ...storage.models import SessionRecord

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("/{approval_id}")
def get_approval_api(approval_id: str, db: Session = Depends(get_db)):
    record = get_approval_service(approval_id, db)
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return record


@router.post("/{approval_id}/approve")
async def approve(approval_id: str, db: Session = Depends(get_db)):
    record = approve_service(approval_id, db)
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return StreamingResponse(
        resume_run_service(approval_id, db, rejected=False),
        media_type="text/event-stream",
    )


@router.post("/{approval_id}/reject")
async def reject(approval_id: str, db: Session = Depends(get_db)):
    record = reject_service(approval_id, db)
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return StreamingResponse(
        resume_run_service(approval_id, db, rejected=True),
        media_type="text/event-stream",
    )


@router.post("/{approval_id}/approve_all")
async def approve_all(approval_id: str, db: Session = Depends(get_db)):
    record = approve_service(approval_id, db)
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    session_record = db.query(SessionRecord).filter(
        SessionRecord.session_id == record.session_id
    ).first()
    if session_record:
        session_record.permission_profile = "full-auto"
        db.commit()
    return StreamingResponse(
        resume_run_service(approval_id, db, rejected=False),
        media_type="text/event-stream",
    )