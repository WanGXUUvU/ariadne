from sqlalchemy.orm import Session

from ..storage.stores.approval_store import SqliteApprovalStore
from ..storage.models import PendingApproval
from typing import Optional


def get_approval_service(approval_id: str, db: Session) -> Optional[PendingApproval]:
    store = SqliteApprovalStore(db)
    return store.get(approval_id)


def approve_service(approval_id: str, db: Session) -> Optional[PendingApproval]:
    store = SqliteApprovalStore(db)
    record = store.update_status(approval_id, "approved")
    if record is None:
        return None
    db.commit()
    return record


def reject_service(approval_id: str, db: Session) -> Optional[PendingApproval]:
    store = SqliteApprovalStore(db)
    record = store.update_status(approval_id, "rejected")
    if record is None:
        return None
    db.commit()
    return record