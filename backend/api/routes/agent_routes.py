"""智能体模板 HTTP 路由适配层。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.agent import (
    AgentDefinition,
    delete_agent_definition,
    list_agent_definitions,
    load_agent_definition,
    save_agent_definition,
)
from backend.infra.db.engine import get_db

router = APIRouter()


@router.get("/agents/{agent_id}")
def load_agent_definition_api(
    agent_id: str,
    db: Session = Depends(get_db),
) -> AgentDefinition:
    """根据智能体 ID 获取其详细配置定义。"""
    return load_agent_definition(
        db=db,
        agent_id=agent_id,
    )


@router.get("/agents")
def list_agents_api(
    db: Session = Depends(get_db),
):
    """获取系统内所有可用的智能体模板列表。"""
    return list_agent_definitions(db=db)


@router.post("/agents", response_model=AgentDefinition)
def save_agent_api(
    definition: AgentDefinition,
    db: Session = Depends(get_db),
):
    """新建或覆盖更新一个智能体模板配置。"""
    return save_agent_definition(
        db=db,
        definition=definition,
    )


@router.delete("/agents/{agent_id}")
def delete_agent_api(
    agent_id: str,
    db: Session = Depends(get_db),
):
    """删除指定的智能体模板配置。"""
    delete_agent_definition(
        db=db,
        agent_id=agent_id,
    )
    return {"status": "ok"}
