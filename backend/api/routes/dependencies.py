"""接口与适配层 (Interface Layer) - FastAPI 路由依赖注入提供者

职责：
1. 提供 FastAPI 专用的 Depends 注入项，统一管理数据库 Session 的生命周期。
2. 提供各个应用层 Service 服务实例的依赖注入创建（如 RunService, SessionService 等）。

不负责：
1. 任何具体的业务逻辑执行或路由控制。
2. 数据库物理连接池的维护。

数据流向：
- 输入：FastAPI 依赖注入机制。
- 输出：应用服务实例（Service）。
- 上游来源：FastAPI 路由网关。
- 下游流向：作为入参被注入到所有的路由控制器中。

架构说明：
- 本文件是 API 层（L9）与基础设施层（L0）之间的唯一合法桥梁。
- 所有路由控制器必须从此文件获取 service 实例，禁止直接 import `infra.db.engine`。
"""

from fastapi import Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from backend.infra.db.engine import get_db
from backend.api.dto.schemas import ApiError, ErrorResponse

# ── Service 导入（L7/L8 应用服务层）───────────────────────────────────────────
from backend.execution.service import RunService
from backend.memory.session.service import SessionService
from backend.memory.summary.service import CompactService
from backend.skills.service import SkillService
from backend.security.approval.service import ApprovalService
from backend.execution.resume.service import ResumeRunService
from backend.agent.definition import AgentDefinitionService
from backend.agent.settings import SettingsService
from backend.mcp.service import McpSettingsService
from backend.memory.workspace.service import WorkspaceService


def error_response(status_code: int, code: str, message: str) -> JSONResponse:
    """生成统一格式的错误响应（JSONResponse）。

    当系统出错或者输入参数不对时，用它可以保证返回给前端的错误格式是一致的，方便前端解析。
    """
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            error=ApiError(
                code=code,
                message=message,
            )
        ).model_dump(),
    )


# ── Service Provider 工厂（供路由层 Depends 注入）─────────────────────────────


def get_run_service(db: Session = Depends(get_db)) -> RunService:
    """提供 RunService 实例（含运行时编排、trace 查询、子 Agent 调度）。"""
    return RunService(db)


def get_session_service(db: Session = Depends(get_db)) -> SessionService:
    """提供 SessionService 实例（含会话 CRUD、状态管理）。"""
    return SessionService(db)


def get_compact_service(db: Session = Depends(get_db)) -> CompactService:
    """提供 CompactService 实例（含历史消息压缩）。"""
    return CompactService(db)


def get_skill_service() -> SkillService:
    """提供 SkillService 实例（含技能列表、启用/禁用）。"""
    return SkillService()


def get_approval_service(db: Session = Depends(get_db)) -> ApprovalService:
    """提供 ApprovalService 实例（含审批查询、同意/拒绝）。"""
    return ApprovalService(db)


def get_resume_run_service(db: Session = Depends(get_db)) -> ResumeRunService:
    """提供 ResumeRunService 实例（含审批后恢复流式运行）。"""
    return ResumeRunService(db)


def get_agent_definition_service(
    db: Session = Depends(get_db),
) -> AgentDefinitionService:
    """提供 AgentDefinitionService 实例（含 Agent 定义 CRUD）。"""
    return AgentDefinitionService(db)


def get_settings_service(db: Session = Depends(get_db)) -> SettingsService:
    """提供 SettingsService 实例（含 Provider/Model 设置）。"""
    return SettingsService(db)


def get_mcp_settings_service() -> McpSettingsService:
    """提供 McpSettingsService 实例（含 MCP 配置与 runtime reload）。"""
    return McpSettingsService()


def get_workspace_service(db: Session = Depends(get_db)) -> WorkspaceService:
    """提供 WorkspaceService 实例（含工作区列表、选择对话框）。"""
    return WorkspaceService(db)
