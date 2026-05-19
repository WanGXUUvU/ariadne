from ...application.approval_service import reject_service,approve_service,get_approval_service
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy.orm import Session
from ...storage.models import PendingApproval
from ...storage.db import get_db
from typing import Optional

router = APIRouter(prefix="/approvals", tags=["approvals"])

@router.get("/{approval_id}")
def get_approval_api(approval_id:str,db:Session=Depends(get_db)):
    record = get_approval_service(approval_id, db)
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return record

@router.post("/{approval_id}/approve")
def approve(approval_id: str, db: Session = Depends(get_db)):
    record = approve_service(approval_id, db)
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return {"ok": True, "status": "approved"}

@router.post("/{approval_id}/reject")
def reject(approval_id: str, db: Session = Depends(get_db)):
    record = reject_service(approval_id, db)
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return {"ok": True, "status": "rejected"}