"""物理工作区接口适配层。
负责承接 HTTP 契约与 DTO 序列化，实例化 WorkspaceService 并分发响应。
"""

from fastapi import APIRouter, Depends, status
from agent_prototype.api.dto.schemas import WorkspaceSummary
from agent_prototype.memory.workspace.service import WorkspaceService
from agent_prototype.api.routes.dependencies import (
    error_response,
    get_workspace_service,
)

router = APIRouter()


@router.get("/workspaces", response_model=list[WorkspaceSummary])
def list_workspace_api(service: WorkspaceService = Depends(get_workspace_service)):
    records = service.list_workspace()
    return [WorkspaceSummary.model_validate(record) for record in records]


@router.post("/workspaces/select-dialog", response_model=WorkspaceSummary)
def select_workspace_dialog_api(
    service: WorkspaceService = Depends(get_workspace_service),
):
    """唤起 macOS 原生 Finder 选择弹窗，自动注册并返回工作区信息。
    若用户取消或超时，则抛出 400 Bad Request。
    """
    record = service.select_dialog()
    if record is None:
        return error_response(
            status.HTTP_400_BAD_REQUEST,
            "dialog_cancelled",
            "User cancelled the folder selection or operation timed out.",
        )
    return WorkspaceSummary.model_validate(record)
