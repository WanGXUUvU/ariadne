"""智能体模板 HTTP 路由适配层。

职责：
- 提供内置与自定义智能体（Agent）模板的 HTTP CRUD 接口。

上游：
- 前端 Agent 管理面板

下游：
- AgentDefinitionService (agent/definition/service)

不负责：
- 不做 Agent 物理定义加载或数据库的直接持久化（由服务层负责）。
- 不做智能体运行时构建及执行编排（由执行层负责）。
"""

from fastapi import APIRouter, Depends

from backend.agent.types import AgentDefinition
from backend.agent.definition import AgentDefinitionService
from backend.api.routes.dependencies import get_agent_definition_service

router = APIRouter()


@router.get("/agents/{agent_id}")
def load_agent_definition_api(
    agent_id: str,
    service: AgentDefinitionService = Depends(get_agent_definition_service),
) -> AgentDefinition:
    """根据智能体 ID 获取其详细配置定义。"""
    return service.load_definition(agent_id)


@router.get("/agents")
def list_agents_api(
    service: AgentDefinitionService = Depends(get_agent_definition_service),
):
    """获取系统内所有可用的智能体模板列表。"""
    return service.list_agents()


@router.post("/agents", response_model=AgentDefinition)
def save_agent_api(
    definition: AgentDefinition,
    service: AgentDefinitionService = Depends(get_agent_definition_service),
):
    """新建或覆盖更新一个智能体模板配置。"""
    return service.save_agent(definition)


@router.delete("/agents/{agent_id}")
def delete_agent_api(
    agent_id: str,
    service: AgentDefinitionService = Depends(get_agent_definition_service),
):
    """删除指定的智能体模板配置。"""
    service.delete_agent(agent_id)
    return {"status": "ok"}
