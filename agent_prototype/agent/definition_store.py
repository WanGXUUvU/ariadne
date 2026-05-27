"""
[九层模型 - 智能体持久化层 (Agent Persistence Layer)]

文件职责：
- 充当自定义智能体定义记录在 SQLite 数据库中的物理读写仓储（SqliteAgentDefinitionStore）。
- 封装 Pydantic 的 `AgentDefinition` 域模型与底层 ORM JSON 字符串（AgentDefinitionRecord）之间的序列化与反序列化转换。

上游依赖：L10 助理服务层 (AgentDefinitionService)。
下游依赖：L0 基础设施 (db / orm_models)。
"""
import json
from typing import Optional
from sqlalchemy.orm import Session

from agent_prototype.infra.db.orm_models import AgentDefinitionRecord
from agent_prototype.agent.definition import AgentDefinition, DEFAULT_AGENT_DEFINITION

class SqliteAgentDefinitionStore:
    def __init__(self,db:Session):
        """输入：数据库会话。输出：初始化后的 SqliteAgentDefinitionStore 实例。"""
        self.db=db

    def get(self,agent_id:str)->Optional[AgentDefinition]:
        """输入：agent_id。输出：匹配到的 AgentDefinition，找不到时返回 None。"""
        record=(
            self.db.query(AgentDefinitionRecord)
            .filter(AgentDefinitionRecord.agent_id==agent_id)
            .first()
        )
        if not record:return None

        data=json.loads(record.definition_json)
        return AgentDefinition.model_validate(data)
    
    def save(self,definition:AgentDefinition)->None:
        """输入：AgentDefinition 对象。输出：无，副作用是把定义写入数据库。"""
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
    
    def list_all(self)->list[AgentDefinition]:
        records=self.db.query(AgentDefinitionRecord).all()
        result = []
        for record in records:
            data=json.loads(record.definition_json)
            result.append(AgentDefinition.model_validate(data))
        return result

    def get_or_default(self)->AgentDefinition:
        """输入：无。输出：default 的 AgentDefinition，不存在时返回内存默认定义。"""
        definition =self.get("default")

        if definition is not None:
            return definition
        
        return DEFAULT_AGENT_DEFINITION
    
    def delete_agent(self,agent_id:str):
        """输入：需要删除的agent_id。 输出：删除的AgentDefinition"""

        record=self.db.query(AgentDefinitionRecord).filter(AgentDefinitionRecord.agent_id==agent_id).first()
        if record:
            self.db.delete(record)