"""接口与适配层 (Interface Layer) - 技能管理路由控制器

职责：
1. 提供技能管理的路由控制器，支持技能的列出、上传、启用/禁用。
2. 进行技能上传的参数与包名验证。

不负责：
1. 技能 Python 模块的物理动态导入。
2. 技能在运行时执行上下文中的参数装配。

数据流向：
- 输入：HTTP 请求及技能动作参数。
- 输出：技能列表或启用状态 JSON 响应。
- 上游来源：前端。
- 下游流向：调用 agent_prototype/skills/service.py。
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from agent_prototype.api.dto.schemas import SkillSummary
from agent_prototype.skills.service import SkillService
from agent_prototype.infra.db.engine import get_db
from agent_prototype.api.routes.dependencies import error_response

router = APIRouter()


@router.get("/skills", response_model=list[SkillSummary])
def list_skills_api(db: Session = Depends(get_db)) -> list[SkillSummary]:
    """这个函数是用来列出系统里所有可用技能（Skill）的。
    
    技能是 Agent 能够执行的某种大任务或复杂业务流，通过这个接口可以方便地查看当前所有已加载技能的状态（比如是否启用等）。
    
    需要拿到的东西：
    - db: 数据库连接会话，用于从数据库里查出所有的技能配置。
    
    会给出来的结果：
    - 包含所有技能概要信息的列表（List[SkillSummary]）。
    """
    service = SkillService(db)
    return service.list_skills()


@router.post("/skills/{skill_name}/disable", response_model=SkillSummary)
def disable_skill_api(skill_name: str, db: Session = Depends(get_db)) -> SkillSummary:
    """这个函数是用来临时禁用某个技能的。
    
    比如你发现某个技能有 Bug，或者暂时不想让 Agent 拥有这个能力，就可以调用这个接口来禁用它。
    
    需要拿到的东西：
    - skill_name: 字符串类型，代表要禁用的技能名称。
    - db: 数据库连接会话。
    
    会给出来的结果：
    - SkillSummary 对象，被禁用后的技能最新状态和配置信息。
    """
    try:
        service = SkillService(db)
        return service.disable_skill(skill_name)
    except ValueError as exc:
        return error_response(status.HTTP_400_BAD_REQUEST, "bad_request", str(exc))


@router.post("/skills/{skill_name}/enable", response_model=SkillSummary)
def enable_skill_api(skill_name: str, db: Session = Depends(get_db)) -> SkillSummary:
    """这个函数是用来启用某个之前被禁用的技能的。
    
    调用这个接口后，Agent 就能重新获得该技能并可以使用它。
    
    需要拿到的东西：
    - skill_name: 字符串类型，代表要启用的技能名称。
    - db: 数据库连接会话。
    
    会给出来的结果：
    - SkillSummary 对象，被启用后的技能最新状态和配置信息。
    """
    try:
        service = SkillService(db)
        return service.enable_skill(skill_name)
    except ValueError as exc:
        return error_response(status.HTTP_400_BAD_REQUEST, "bad_request", str(exc))