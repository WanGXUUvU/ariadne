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
from sqlalchemy.orm import Session

from agent_prototype.infra.db.engine import get_db
from agent_prototype.agent.definition import AgentDefinition
from agent_prototype.agent.definition_service import AgentDefinitionService

router = APIRouter()


@router.get("/agents/{agent_id}")
def load_agent_definition_api(agent_id: str, db: Session = Depends(get_db)) -> AgentDefinition:
    service = AgentDefinitionService(db)
    return service.load_definition(agent_id)


@router.get("/agents")
def list_agents_api(db: Session = Depends(get_db)):
    service = AgentDefinitionService(db)
    return service.list_agents()


@router.post("/agents", response_model=AgentDefinition)
def save_agent_api(definition: AgentDefinition, db: Session = Depends(get_db)):
    service = AgentDefinitionService(db)
    return service.save_agent(definition)


@router.delete("/agents/{agent_id}")
def delete_agent_api(agent_id: str, db: Session = Depends(get_db)):
    service = AgentDefinitionService(db)
    service.delete_agent(agent_id)
    return {"status": "ok"}