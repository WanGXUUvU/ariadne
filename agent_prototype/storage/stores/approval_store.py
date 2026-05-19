import uuid
from typing import Optional

from sqlalchemy.orm import Session

from ..models import PendingApproval

class SqliteApprovalStore:

    def __init__(self,db:Session):
        self.db=db
    
    def create(
            self,
            session_id:str,
            run_id:str,
            tool_name:str,
            arguments:str,
    )->PendingApproval:
        
        record=PendingApproval(
            id=uuid.uuid4().hex,
            session_id=session_id,
            run_id=run_id,
            tool_name=tool_name,
            arguments=arguments,
            status="pending",
        )

        self.db.add(record)

        return record
    
    def get(self,approval_id:str)->Optional[PendingApproval]:

        return (self.db.query(PendingApproval).filter(PendingApproval.id==approval_id).first())
    
    def update_status(self,approval_id:str,status:str)->Optional[PendingApproval]:

        record=self.get(approval_id)
        if record is None:
            return None
        record.status=status
        return record