"""接口与适配层 (Interface Layer) - Agent 模板路由控制器

职责：
1. 提供内置与自定义 Agent 模板的 CRUD API 路由。
2. 管理 Agent 描述的序列化转换，对输入进行 Pydantic 过滤。

不负责：
1. Agent 模板的物理文件加载或数据库直接持久化。
2. Agent 执行器的运行时初始化。

数据流向：
- 输入：HTTP CRUD 请求及 Agent 描述 DTO。
- 输出：Agent 模版列表或操作成功 JSON。
- 上游来源：前端 Agent 管理面板。
- 下游流向：调用 agent_prototype/agent/definition_service.py。
"""

from fastapi import APIRouter, Depends

from agent_prototype.core.types import AgentDefinition
from agent_prototype.agent.definition import AgentDefinitionService
from agent_prototype.api.routes.dependencies import get_agent_definition_service

router = APIRouter()


@router.get("/agents/{agent_id}")
def load_agent_definition_api(agent_id: str, service: AgentDefinitionService = Depends(get_agent_definition_service)) -> AgentDefinition:
    """这个函数是用来加载指定 ID 的 Agent 模板定义的。
    
    简单来说，你给它一个 Agent 的 ID，它就去数据库或系统里把这个 Agent 的所有配置（比如名字、描述、能用什么工具等）都找出来给你。
    
    需要拿到的东西：
    - agent_id: 字符串类型，也就是你要找的那个 Agent 的唯一身份证。
    - service: AgentDefinitionService 实例，由依赖注入提供。
    
    会给出来的结果：
    - AgentDefinition 对象，里面装着这个 Agent 的详细定义和配置信息。
    """
    return service.load_definition(agent_id)


@router.get("/agents")
def list_agents_api(service: AgentDefinitionService = Depends(get_agent_definition_service)):
    """这个函数是用来列出系统里所有可用的 Agent 模板的。
    
    就像去餐厅看菜单一样，它会把所有的 Agent 列表都拿出来展示给你。
    
    需要拿到的东西：
    - service: AgentDefinitionService 实例，由依赖注入提供。
    
    会给出来的结果：
    - 包含所有 Agent 模板的列表（List），每个元素都是一个 Agent 的定义信息。
    """
    return service.list_agents()


@router.post("/agents", response_model=AgentDefinition)
def save_agent_api(definition: AgentDefinition, service: AgentDefinitionService = Depends(get_agent_definition_service)):
    """这个函数是用来保存或者创建一个 Agent 模板定义的。
    
    如果你设计了一个新的 Agent，或者改了它的配置，调用这个接口就能把它存进系统里。
    
    需要拿到的东西：
    - definition: AgentDefinition 对象，就是你要保存的那个 Agent 的完整配置和定义。
    - service: AgentDefinitionService 实例，由依赖注入提供。
    
    会给出来的结果：
    - 保存成功后，会把这个存好的 Agent 模板定义原样或更新后返回给你，确认保存成功。
    """
    return service.save_agent(definition)


@router.delete("/agents/{agent_id}")
def delete_agent_api(agent_id: str, service: AgentDefinitionService = Depends(get_agent_definition_service)):
    """这个函数是用来删除一个 Agent 模板定义的。
    
    如果你不需要某个 Agent 了，用这个接口给它送走。
    
    需要拿到的东西：
    - agent_id: 字符串类型，也就是你要删掉的那个 Agent 的唯一身份证。
    - service: AgentDefinitionService 实例，由依赖注入提供。
    
    会给出来的结果：
    - 一个简单的字典信息，比如 {"status": "ok"}，告诉你已经成功删除了。
    """
    service.delete_agent(agent_id)
    return {"status": "ok"}