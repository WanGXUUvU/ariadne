from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from agent_prototype.infra.db.engine import get_db
from agent_prototype.security.approval.service import ApprovalService
from agent_prototype.execution.resume.resume_run_service import ResumeRunService

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("/{approval_id}")
def get_approval_api(approval_id: str, db: Session = Depends(get_db)):
    service = ApprovalService(db)
    record = service.get_approval(approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return record


@router.post("/{approval_id}/approve")
async def approve(approval_id: str, db: Session = Depends(get_db)):
    service = ApprovalService(db)
    record = service.approve(approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return StreamingResponse(
        ResumeRunService(db).resume_run(approval_id, rejected=False),
        media_type="text/event-stream",
    )


@router.post("/{approval_id}/reject")
async def reject(approval_id: str, db: Session = Depends(get_db)):
    service = ApprovalService(db)
    record = service.reject(approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return StreamingResponse(
        ResumeRunService(db).resume_run(approval_id, rejected=True),
        media_type="text/event-stream",
    )


@router.post("/{approval_id}/approve_all")
async def approve_all(approval_id: str, db: Session = Depends(get_db)):
    service = ApprovalService(db)
    record = service.approve_all(approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return StreamingResponse(
        ResumeRunService(db).resume_run(approval_id, rejected=False),
        media_type="text/event-stream",
    )