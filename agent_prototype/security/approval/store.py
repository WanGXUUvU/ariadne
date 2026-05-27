import uuid,json
from typing import Optional

from sqlalchemy.orm import Session

from agent_prototype.infra.db.orm_models import PendingApproval
from agent_prototype.api.dto.schemas import ChatMessage

class SqliteApprovalStore:

    def __init__(self,db:Session):
        self.db=db
    
    def create(
            self,
            session_id:str,
            run_id:str,
            tool_name:str,
            tool_call_id:str,
            arguments:str,
            saved_messages:list[ChatMessage],
            event_index:int,
    )->PendingApproval:
        
        record=PendingApproval(
            id=uuid.uuid4().hex,
            session_id=session_id,
            run_id=run_id,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            arguments=arguments,
            status="pending",
            saved_messages=[saved_message.model_dump(exclude_none=True) for saved_message in saved_messages],
            event_index=event_index,
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
    
    def restore_messages(self,approval:PendingApproval)->list[ChatMessage]:

        return [ChatMessage.model_validate(msg) for msg in approval.saved_messages]