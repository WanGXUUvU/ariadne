from ...storage.db import get_db
from fastapi import APIRouter,Depends
from ...core.agent_definition import AgentDefinition
from ...application.agent_definition_service import load_agent_definition_service,list_agents_service,save_agent_service,delete_agent_service
from sqlalchemy.orm import Session

router=APIRouter()

@router.get("/agents/{agent_id}")
def load_agent_definition_api(agent_id:str,db:Session=Depends(get_db))->AgentDefinition:
    return load_agent_definition_service(agent_id,db)

@router.get("/agents")
def list_agents_api(db:Session=Depends(get_db)):
    return list_agents_service(db)

@router.post("/agents",response_model=AgentDefinition)
def save_agent_api(definition:AgentDefinition,db:Session=Depends(get_db)):
    return save_agent_service(definition,db)

@router.delete("/agents/{agent_id}")
def delete_agent_api(agent_id:str,db:Session=Depends(get_db)):
    return delete_agent_service(agent_id,db)