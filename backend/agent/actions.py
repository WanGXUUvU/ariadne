"""处理 Agent 定义相关动作。"""

from sqlalchemy.orm import Session

from backend.agent.types import AgentDefinition, DEFAULT_AGENT_DEFINITION
from backend.agent.loader import list_builtin_agents
from backend.agent.store import SqliteAgentDefinitionStore


def load_agent_definition(db: Session, agent_id: str) -> AgentDefinition:
    """按 ID 读取一个 Agent 定义。"""
    definition = SqliteAgentDefinitionStore(db).get(agent_id=agent_id)
    if definition is not None:
        return definition

    builtins = {agent.id: agent for agent in list_builtin_agents()}
    if agent_id in builtins:
        return builtins[agent_id]
    if agent_id == DEFAULT_AGENT_DEFINITION.id:
        return DEFAULT_AGENT_DEFINITION
    raise ValueError(f"Unknown agent definition: {agent_id}")


def list_agent_definitions(db: Session) -> list[AgentDefinition]:
    """列出合并后的内置和自定义 Agent 定义。"""
    merged = {
        agent.id: agent.model_copy(update={"is_builtin": True})
        for agent in list_builtin_agents()
    }
    for agent in SqliteAgentDefinitionStore(db).list_all():
        merged[agent.id] = agent
    return list(merged.values())


def save_agent_definition(db: Session, definition: AgentDefinition) -> AgentDefinition:
    """保存一个自定义 Agent 定义。"""
    SqliteAgentDefinitionStore(db).save(definition=definition)
    db.commit()
    return definition


def delete_agent_definition(db: Session, agent_id: str) -> None:
    """删除一个自定义 Agent 定义。"""
    SqliteAgentDefinitionStore(db).delete_agent(agent_id=agent_id)
    db.commit()
