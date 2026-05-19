import json
from sqlalchemy.orm import Session
from ..agents.agent_loader import list_builtin_agents
from ..core.agent_definition import AgentDefinition
from ..storage.stores.agent_definition_store import SqliteAgentDefinitionStore



def load_agent_definition_service(agent_id: str, db: Session) -> AgentDefinition:  # 按名字加载 agent 定义
    """输入：agent 名称、数据库会话。输出：匹配到的 AgentDefinition。"""
    store = SqliteAgentDefinitionStore(db)  # 创建定义存储器

    definition = store.get(agent_id)  # 只查一次数据库
    if definition is not None:  # 如果查到了
        return definition  # 直接返回
    builtins={a.id: a for a in list_builtin_agents()}
    if agent_id in builtins:  # default 允许回退
        return builtins[agent_id]  # 回退内存默认定义

    raise ValueError(f"Unknown agent definition: {agent_id}")  # 其他名字不存在就报错

def list_agents_service(db: Session) -> list[AgentDefinition]:
    """输入：数据库会话。输出：builtin + DB 合并后的 AgentDefinition 列表，DB 优先。"""
    store = SqliteAgentDefinitionStore(db)
    # builtin 打底，标记 is_builtin=True
    merged = {a.id: a.model_copy(update={"is_builtin": True}) for a in list_builtin_agents()}
    for a in store.list_all():  # DB 同 id 覆盖，DB 来的 is_builtin=False
        merged[a.id] = a
    return list(merged.values())

def delete_agent_service(agent_id:str,db:Session):
    store=SqliteAgentDefinitionStore(db)
    store.delete_agent(agent_id)
    db.commit()

def save_agent_service(definition:AgentDefinition,db:Session)->AgentDefinition:
    store=SqliteAgentDefinitionStore(db)
    store.save(definition)
    db.commit()
    return definition
