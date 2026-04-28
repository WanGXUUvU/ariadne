import json
from sqlalchemy.orm import Session

from ..core.agent_definition import AgentDefinition, DEFAULT_AGENT_DEFINITION
from ..storage.agent_definition_store import SqliteAgentDefinitionStore

def load_agent_definition(agent_name: str, db: Session) -> AgentDefinition:  # 按名字加载 agent 定义
    store = SqliteAgentDefinitionStore(db)  # 创建定义存储器

    definition = store.get(agent_name)  # 只查一次数据库
    if definition is not None:  # 如果查到了
        return definition  # 直接返回

    if agent_name == "default":  # default 允许回退
        return DEFAULT_AGENT_DEFINITION  # 回退内存默认定义

    raise ValueError(f"Unknown agent definition: {agent_name}")  # 其他名字不存在就报错
