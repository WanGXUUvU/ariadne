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

from backend.infra.db.orm_models import AgentDefinitionRecord
from backend.agent.types import AgentDefinition, DEFAULT_AGENT_DEFINITION


class SqliteAgentDefinitionStore:
    """这个类是自定义 Agent 配置的数据库底层保险箱（Sqlite 仓储实现）。

    它唯一的任务就是老老实实地跟 SQLite 数据库打交道，把高级的 Python AgentDefinition 对象翻译成底层的 JSON 字符串存进数据库，或者从数据库读取 JSON 字符串再翻译回 Python 对象。

    它的上下游：
    - 上游：AgentDefinitionService 服务大管家。
    - 下游：数据库物理表的 ORM 模型 AgentDefinitionRecord。
    """

    def __init__(self, db: Session):
        """保险箱的初始化函数，把数据库连接会话存起来，方便随时调用。

        需要拿到的东西：
        - db: 数据库连接会话，用于执行 SQL 增删改查。

        会给出来的结果：
        - 仓储类实例本身。
        """
        self.db = db

    def get(self, agent_id: str) -> Optional[AgentDefinition]:
        """根据 ID 去数据库中查找并取出对应的 Agent 配置。

        需要拿到的东西：
        - agent_id: 字符串，你要查找的那个 Agent 唯一 ID。

        会给出来的结果：
        - 找到的话，会翻译并返回一个 AgentDefinition 配置对象；要是数据库里压根没这条记录，就返回 None。
        """
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
        """把一个 Python 的 Agent 配置对象保存到数据库中。

        如果这个 ID 的 Agent 已经在数据库里了，就用新配置覆盖它；如果还没有，就新建一条记录。

        需要拿到的东西：
        - definition: AgentDefinition 对象，也就是要存盘的 Agent 完整配置。

        会给出来的结果：
        - 无返回值，它的作用是产生数据库写入或更新的副作用。
        """
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
        """把数据库中所有保存的自定义 Agent 配置一次性全部拿出来。

        需要拿到的东西：
        - 无需额外参数。

        会给出来的结果：
        - 包含数据库中所有自定义 Agent 配置对象的列表（List[AgentDefinition]）。
        """
        records = self.db.query(AgentDefinitionRecord).all()
        result = []
        for record in records:
            data = json.loads(record.definition_json)
            result.append(AgentDefinition.model_validate(data))
        return result

    def get_or_default(self) -> AgentDefinition:
        """获取默认的 Agent 配置（ID 为 'default'）。

        如果数据库里没有配默认 Agent，它就会返回系统内存中那个最基础的备用 Agent。

        需要拿到的东西：
        - 无需额外参数。

        会给出来的结果：
        - 最终拿到的 AgentDefinition 默认配置对象。
        """
        definition = self.get("default")

        if definition is not None:
            return definition

        return DEFAULT_AGENT_DEFINITION

    def delete_agent(self, agent_id: str):
        """从数据库中永久物理删掉指定 ID 的自定义 Agent 配置记录。

        需要拿到的东西：
        - agent_id: 字符串，你想删掉的自定义 Agent 的 ID。

        会给出来的结果：
        - 无返回值（执行成功后会将该记录从数据库中删除）。
        """

        record = (
            self.db.query(AgentDefinitionRecord)
            .filter(AgentDefinitionRecord.agent_id == agent_id)
            .first()
        )
        if record:
            self.db.delete(record)
