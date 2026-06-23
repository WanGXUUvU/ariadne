"""配置模块 HTTP 路由适配层。

职责：
- 提供模型提供商（Provider）及具体模型（Model）配置的 HTTP CRUD 与同步接口。

上游：
- 前端全局设置抽屉面板

下游：
- SettingsService (agent/settings/service)

不负责：
- 不做任何全局配置项的直接 SQL 操作与磁盘持久化（由服务与仓储层负责）。
- 不验证业务规则（如 API Key 结构真实性等）。
"""

from typing import Optional
from fastapi import APIRouter, Depends, status

from backend.agent.settings.types import ModelOut, ProviderOut
from backend.api.dto.schemas import (
    CreateProviderInput,
    CreateMcpServerInput,
    McpReloadOut,
    McpServerOut,
    PatchModelInput,
    PatchMcpServerInput,
    PatchProviderInput,
)
from backend.agent.settings import SettingsService
from backend.mcp.service import McpSettingsService
from backend.api.routes.dependencies import (
    error_response,
    get_mcp_settings_service,
    get_settings_service,
)

router = APIRouter(prefix="/settings")


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


@router.post(
    "/providers", response_model=ProviderOut, status_code=status.HTTP_201_CREATED
)
def create_provider_api(
    payload: CreateProviderInput,
    service: SettingsService = Depends(get_settings_service),
) -> ProviderOut:
    """注册并添加一个新的大模型供应商（Provider）配置。"""
    return service.create_provider(
        name=payload.name,
        base_url=payload.base_url,
        api_key=payload.api_key,
    )


@router.get("/providers", response_model=list[ProviderOut])
def list_providers_api(
    service: SettingsService = Depends(get_settings_service),
) -> list[ProviderOut]:
    """列出系统里所有已注册的大模型供应商列表。"""
    return service.list_providers()


@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider_api(
    provider_id: int, service: SettingsService = Depends(get_settings_service)
) -> None:
    """物理删除指定 ID 的大模型供应商记录。"""
    try:
        service.delete_provider(provider_id)
    except ValueError as exc:
        return error_response(status.HTTP_404_NOT_FOUND, "provider_not_found", str(exc))


@router.patch("/providers/{provider_id}", response_model=ProviderOut)
def patch_provider_api(
    provider_id: int,
    payload: PatchProviderInput,
    service: SettingsService = Depends(get_settings_service),
) -> ProviderOut:
    """更新指定大模型供应商的属性（名字、接口地址、API 密钥等）。"""
    try:
        return service.patch_provider(
            provider_id,
            name=payload.name,
            base_url=payload.base_url,
            api_key=payload.api_key,
            is_default=payload.is_default,
        )
    except ValueError as exc:
        return error_response(status.HTTP_404_NOT_FOUND, "provider_not_found", str(exc))


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


@router.get("/providers/{provider_id}/models", response_model=list[ModelOut])
def sync_provider_models_api(
    provider_id: int, service: SettingsService = Depends(get_settings_service)
) -> list[ModelOut]:
    """请求供应商的 models 接口同步其所支持的所有可用文本模型到本地数据库。"""
    try:
        return service.sync_provider_models(provider_id)
    except ValueError as exc:
        return error_response(status.HTTP_404_NOT_FOUND, "provider_not_found", str(exc))


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


@router.get("/models", response_model=list[ModelOut])
def list_models_api(
    provider_id: Optional[int] = None,
    enabled: Optional[bool] = None,
    service: SettingsService = Depends(get_settings_service),
) -> list[ModelOut]:
    """列出本地数据库保存的所有已同步模型列表，支持按供应商或启用状态过滤。"""
    return service.list_models(provider_id=provider_id, enabled_only=enabled is True)


@router.patch("/models/{model_id}", response_model=ModelOut)
def patch_model_api(
    model_id: int,
    payload: PatchModelInput,
    service: SettingsService = Depends(get_settings_service),
) -> ModelOut:
    """修改指定模型的启用状态或在界面上的显示名称（中文别名）。"""
    try:
        return service.patch_model(
            model_id,
            enabled=payload.enabled,
            display_name=payload.display_name,
        )
    except ValueError as exc:
        return error_response(status.HTTP_404_NOT_FOUND, "model_not_found", str(exc))


# ---------------------------------------------------------------------------
# MCP Servers
# ---------------------------------------------------------------------------


@router.get("/mcp/servers", response_model=list[McpServerOut])
def list_mcp_servers_api(
    service: McpSettingsService = Depends(get_mcp_settings_service),
) -> list[McpServerOut]:
    """列出全部 MCP server 配置摘要及其运行时状态。"""
    return service.list_servers()


@router.get("/mcp/servers/{server_id}", response_model=McpServerOut)
def get_mcp_server_api(
    server_id: str,
    service: McpSettingsService = Depends(get_mcp_settings_service),
) -> McpServerOut:
    """读取单条 MCP server 详情。"""
    try:
        return service.get_server(server_id)
    except LookupError as exc:
        return error_response(status.HTTP_404_NOT_FOUND, "mcp_server_not_found", str(exc))


@router.post(
    "/mcp/servers",
    response_model=McpServerOut,
    status_code=status.HTTP_201_CREATED,
)
def create_mcp_server_api(
    payload: CreateMcpServerInput,
    service: McpSettingsService = Depends(get_mcp_settings_service),
) -> McpServerOut:
    """新增一条 MCP server 配置。"""
    try:
        return service.create_server(payload.model_dump())
    except ValueError as exc:
        return error_response(status.HTTP_400_BAD_REQUEST, "invalid_mcp_server", str(exc))


@router.patch("/mcp/servers/{server_id}", response_model=McpServerOut)
def patch_mcp_server_api(
    server_id: str,
    payload: PatchMcpServerInput,
    service: McpSettingsService = Depends(get_mcp_settings_service),
) -> McpServerOut:
    """局部更新一条 MCP server 配置。"""
    try:
        return service.patch_server(server_id, payload.model_dump(exclude_unset=True))
    except LookupError as exc:
        return error_response(status.HTTP_404_NOT_FOUND, "mcp_server_not_found", str(exc))
    except ValueError as exc:
        return error_response(status.HTTP_400_BAD_REQUEST, "invalid_mcp_server", str(exc))


@router.delete("/mcp/servers/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mcp_server_api(
    server_id: str,
    service: McpSettingsService = Depends(get_mcp_settings_service),
) -> None:
    """删除一条 MCP server 配置。"""
    try:
        service.delete_server(server_id)
    except LookupError as exc:
        return error_response(status.HTTP_404_NOT_FOUND, "mcp_server_not_found", str(exc))


@router.post("/mcp/reload", response_model=McpReloadOut)
def reload_mcp_runtime_api(
    service: McpSettingsService = Depends(get_mcp_settings_service),
) -> McpReloadOut:
    """按最新 settings.json 重新启动 MCP runtime。"""
    try:
        return service.reload_runtime()
    except Exception as exc:
        return error_response(status.HTTP_400_BAD_REQUEST, "mcp_reload_failed", str(exc))


# ---------------------------------------------------------------------------
# Settings.json File Management
# ---------------------------------------------------------------------------

from backend.infra.config.settings import load_settings, save_settings

@router.get("/file")
def get_settings_file_api() -> dict:
    """获取完整的 settings.json 配置数据。"""
    return load_settings()


@router.post("/file")
def update_settings_file_api(payload: dict) -> dict:
    """更新完整的 settings.json 配置数据。"""
    save_settings(payload)
    return {"status": "success"}
