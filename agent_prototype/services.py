from .session_store import SqliteSessionStore
from .schemas import AgentInput,AgentOutput,AgentState,ResetInput
from .agent import Agent
from .agent_loader import load_agent_definition
from sqlalchemy.orm import Session


def run_agent_service(agent_input:AgentInput,db:Session)-> AgentOutput:
    store = SqliteSessionStore(db) #用数据库会话创建存储器
    state =store.get(agent_input.session_id) or AgentState()
    effective_agent_name=agent_input.agent_name or "default"
    definiton =load_agent_definition(effective_agent_name,db)
    agent =Agent(state=state,definition=definiton)
    output=agent.run(agent_input)
    output.state.agent_name=effective_agent_name
    store.save(agent_input.session_id,state=output.state)
    return output

def reset_session_service(payload:ResetInput,db:Session)->dict[str,bool]:
    store=SqliteSessionStore(db)
    store.delete(payload.session_id)
    return {"ok":True}

