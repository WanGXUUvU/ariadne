"""读写自定义 Agent 定义。"""

import json
from typing import Optional
from sqlalchemy.orm import Session

from backend.infra.db.orm_models import AgentDefinitionRecord
from backend.agent.types import AgentDefinition, DEFAULT_AGENT_DEFINITION


class SqliteAgentDefinitionStore:
    """用于智能体定义的数据库仓储。"""

    def __init__(self, db: Session):
        """保存数据库会话。"""
        self.db = db

    def get(self, agent_id: str) -> Optional[AgentDefinition]:
        """按 ID 读取 Agent 定义。"""
        record = (
            self.db.query(AgentDefinitionRecord)
            .filter(AgentDefinitionRecord.agent_id == agent_id)
            .first()
        )
        if not record:
            return None

        data = json.loads(record.definition_json)
        return AgentDefinition.model_validate(data)

    def save(self, definition: AgentDefinition) -> None:
        """保存或覆盖 Agent 定义。"""
        definition_json = json.dumps(  # 把字典转换成json
            definition.model_dump(), ensure_ascii=False  # 先把Pydantic对象转换成字典
        )

        record = (
            self.db.query(AgentDefinitionRecord)
            .filter(AgentDefinitionRecord.agent_id == definition.id)
            .first()
        )

        if not record:
            record = AgentDefinitionRecord(
                agent_id=definition.id,
                definition_json=definition_json,
            )
            self.db.add(record)
        else:
            record.definition_json = definition_json

    def list_all(self) -> list[AgentDefinition]:
        """列出所有自定义 Agent 定义。"""
        records = self.db.query(AgentDefinitionRecord).all()
        result = []
        for record in records:
            data = json.loads(record.definition_json)
            result.append(AgentDefinition.model_validate(data))
        return result

    def get_or_default(self) -> AgentDefinition:
        """读取默认 Agent 定义，不存在则返回内置默认值。"""
        definition = self.get(agent_id="default")

        if definition is not None:
            return definition

        return DEFAULT_AGENT_DEFINITION

    def delete_agent(self, agent_id: str) -> bool:
        """删除指定 Agent 定义。"""

        record = (
            self.db.query(AgentDefinitionRecord)
            .filter(AgentDefinitionRecord.agent_id == agent_id)
            .first()
        )
        if record:
            self.db.delete(record)
            return True
        return False
