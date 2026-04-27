import json
from typing import Optional
from sqlalchemy.orm import Session

from .models import AgentDefinitionRecord
from .agent_definition import AgentDefinition,DEFAULT_AGENT_DEFINITION

class SqliteAgentDefinitionStore:
    def __init__(self,db:Session):
        self.db=db

    def get(self,agent_id:str)->Optional[AgentDefinition]:
        record=(
            self.db.query(AgentDefinitionRecord)
            .filter(AgentDefinitionRecord.agent_id==agent_id)
            .first()
        )
        if not record:return None

        data=json.loads(record.definition_json)
        return AgentDefinition.model_validate(data)
    
    def save(self,definition:AgentDefinition)->None:
        definition_json=json.dumps(#把字典转换成json
            definition.model_dump(),#先把Pydantic对象转换成字典
            ensure_ascii=False
        )

        record=self.db.query(AgentDefinitionRecord).filter(AgentDefinitionRecord.agent_id==definition.id).first()

        if not record:
            record=AgentDefinitionRecord(
                agent_id=definition.id,
                definition_json=definition_json,
            )
            self.db.add(record)
        else:
            record.definition_json=definition_json

        self.db.commit()
        

    def get_or_default(self)->AgentDefinition:
        definition =self.get("default")

        if definition is not None:
            return definition
        
        return DEFAULT_AGENT_DEFINITION