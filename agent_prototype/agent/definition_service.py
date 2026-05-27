"""
[九层模型 - 智能体定义层 (Agent Definition Layer)]

文件职责：
- 充当 Agent 静态预设定义的 CRUD 服务（AgentDefinitionService）。
- 统筹 Built-in 内置智能体人设（从 .md 中解析）与 SQLite 数据库自定义智能体人设的查询与合并。

上游依赖：L8 执行层 (RunContextBuilder)、L10 API 接口层。
下游依赖：L10 助理定义仓储层 (SqliteAgentDefinitionStore)、L0 基础设施 (db)。
"""
import json
from sqlalchemy.orm import Session
from agent_prototype.agent.loader import list_builtin_agents
from agent_prototype.agent.definition import AgentDefinition
from agent_prototype.agent.definition_store import SqliteAgentDefinitionStore


class AgentDefinitionService:
    """Agent 定义管理服务类
    
    职责：
    1. 负责 Built-in 内存默认配置与 SQLite 数据库自定义 Agent 配置的智能合并与读取；
    2. 提供高内聚的面向对象 CRUD 接口。
    """
    
    def __init__(self, db: Session):
        """构造函数依赖注入：传入 SQLAlchemy db 会话，聚合仓储实例"""
        self.db = db
        self.store = SqliteAgentDefinitionStore(db)

    def load_definition(self, agent_id: str) -> AgentDefinition:
        """输入：agent_id。输出：匹配到的 AgentDefinition。
        
        首先尝试从数据库加载自定义配置，如果不存在则优雅回退至 Built-in 内存内置配置。
        """
        definition = self.store.get(agent_id)
        if definition is not None:
            return definition
            
        builtins = {a.id: a for a in list_builtin_agents()}
        if agent_id in builtins:
            return builtins[agent_id]

        raise ValueError(f"Unknown agent definition: {agent_id}")

    def list_agents(self) -> list[AgentDefinition]:
        """输出：合并后的 Agent 列表 (Built-in + DB 自定义)
        
        若存在同名自定义 Agent，则无条件覆盖 Built-in 内置定义。
        """
        # 内置定义默认打底，标记为 is_builtin = True
        merged = {a.id: a.model_copy(update={"is_builtin": True}) for a in list_builtin_agents()}
        
        # 遍历数据库自定义，覆盖同 id 记录，标记 is_builtin = False
        for a in self.store.list_all():
            merged[a.id] = a
        return list(merged.values())

    def delete_agent(self, agent_id: str) -> None:
        """输入：agent_id。物理删除数据库中的自定义定义"""
        self.store.delete_agent(agent_id)
        self.db.commit()

    def save_agent(self, definition: AgentDefinition) -> AgentDefinition:
        """输入：AgentDefinition 实体。持久化保存并提交事务"""
        self.store.save(definition)
        self.db.commit()
        return definition

