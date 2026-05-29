"""
[九层模型 - 智能体定义层 (Agent Definition Layer)]

文件职责：
- 充当 Agent 静态预设定义的 CRUD 服务（AgentDefinitionService）。
- 统筹 Built-in 内置智能体人设（从 .md 中解析）与 SQLite 数据库自定义智能体人设的查询与合并。

上游依赖：L8 执行层 (RuntimeContextFactory)、L10 API 接口层。
下游依赖：L10 助理定义仓储层 (SqliteAgentDefinitionStore)、L0 基础设施 (db)。
"""

from sqlalchemy.orm import Session
from agent_prototype.agent.definition.loader import list_builtin_agents
from agent_prototype.agent.types import AgentDefinition
from agent_prototype.agent.definition.store import SqliteAgentDefinitionStore


class AgentDefinitionService:
    """这个类是用来管理和操作 Agent 模板定义配置的服务大管家（CRUD 业务逻辑）。

    它负责把系统内置的 Agent（比如放在 markdown 里的默认配置）和你在后台数据库里自己创建/改过的自定义 Agent 进行大合流与调度，提供统一的增删改查服务。

    它的上下游：
    - 上游：路由层或执行引擎，用来加载需要的 Agent 配置。
    - 下游：底层数据库仓储层，用于执行持久化存取。
    """

    def __init__(self, db: Session):
        """大管家初始化时需要把数据库会话带进来，方便我们在里面读写数据。

        需要拿到的东西：
        - db: 数据库连接会话，用来与数据库进行读写交互。

        会给出来的结果：
        - 服务类实例本身。
        """
        self.db = db
        self.store = SqliteAgentDefinitionStore(db)

    def load_definition(self, agent_id: str) -> AgentDefinition:
        """根据 ID 把对应的 Agent 详细配置加载出来。

        它的逻辑是：先去数据库里找你自定义修改过的 Agent 记录；如果没找到，就去看看是不是系统内置的 Agent 预设；如果还没找到，就报错。

        需要拿到的东西：
        - agent_id: 字符串，你要加载的 Agent 的唯一 ID 身份证。

        会给出来的结果：
        - AgentDefinition 对象，包含了这个 Agent 的完整配置（提示词、名称等）。
        """
        definition = self.store.get(agent_id)
        if definition is not None:
            return definition

        builtins = {a.id: a for a in list_builtin_agents()}
        if agent_id in builtins:
            return builtins[agent_id]

        raise ValueError(f"Unknown agent definition: {agent_id}")

    def list_agents(self) -> list[AgentDefinition]:
        """列出系统里目前所有能用的 Agent 列表。

        它会把"系统自带的"和"你在数据库里自己建的"合并在一起。如果某个你自己建的 Agent 的 ID 和系统自带的一样，它会聪明地用你自定义的配置去覆盖系统自带的。

        需要拿到的东西：
        - 无需额外输入。

        会给出来的结果：
        - 合并后的所有 Agent 详细配置对象列表（List[AgentDefinition]）。
        """
        # 内置定义默认打底，标记为 is_builtin = True
        merged = {a.id: a.model_copy(update={"is_builtin": True}) for a in list_builtin_agents()}

        # 遍历数据库自定义，覆盖同 id 记录，标记 is_builtin = False
        for a in self.store.list_all():
            merged[a.id] = a
        return list(merged.values())

    def delete_agent(self, agent_id: str) -> None:
        """删除一个你在数据库里自定义的 Agent 配置。

        需要拿到的东西：
        - agent_id: 字符串，你想干掉的那个自定义 Agent 的唯一 ID。

        会给出来的结果：
        - 无返回值（执行成功后会将删除操作提交给数据库物理保存）。
        """
        self.store.delete_agent(agent_id)
        self.db.commit()

    def save_agent(self, definition: AgentDefinition) -> AgentDefinition:
        """保存或者修改一个 Agent 模板定义，把它写入数据库进行持久化。

        需要拿到的东西：
        - definition: AgentDefinition 对象，你想保存的完整 Agent 描述信息。

        会给出来的结果：
        - 写入数据库成功后的 AgentDefinition 对象。
        """
        self.store.save(definition)
        self.db.commit()
        return definition
