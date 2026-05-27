from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from agent_prototype.infra.db.engine import get_db
from agent_prototype.agent.definition import AgentDefinition
from agent_prototype.agent.definition_service import AgentDefinitionService

router = APIRouter()


@router.get("/agents/{agent_id}")
def load_agent_definition_api(agent_id: str, db: Session = Depends(get_db)) -> AgentDefinition:
    service = AgentDefinitionService(db)
    return service.load_definition(agent_id)


@router.get("/agents")
def list_agents_api(db: Session = Depends(get_db)):
    service = AgentDefinitionService(db)
    return service.list_agents()


@router.post("/agents", response_model=AgentDefinition)
def save_agent_api(definition: AgentDefinition, db: Session = Depends(get_db)):
    service = AgentDefinitionService(db)
    return service.save_agent(definition)


@router.delete("/agents/{agent_id}")
def delete_agent_api(agent_id: str, db: Session = Depends(get_db)):
    service = AgentDefinitionService(db)
    service.delete_agent(agent_id)
    return {"status": "ok"}