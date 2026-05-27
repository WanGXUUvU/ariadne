"""接口与适配层 (Interface Layer) - 配置路由控制器

职责：
1. 提供全局系统设置（API Key, 模型参数等）的 HTTP 路由控制器。
2. 处理设置的获取与保存请求，保证入参符合 DTO 强约束。

不负责：
1. 系统设置的本地物理持久化或磁盘读写。
2. 设置字段的高级业务逻辑验证。

数据流向：
- 输入：HTTP GET / PUT 请求及 Settings DTO。
- 输出：HTTP JSON 响应。
- 上游来源：前端设置抽屉面板。
- 下游流向：调用 agent_prototype/agent/settings_service.py 进行业务处理。
"""

from typing import Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from agent_prototype.api.dto.schemas import CreateProviderInput, ModelOut, PatchModelInput, PatchProviderInput, ProviderOut
from agent_prototype.agent.settings_service import SettingsService
from agent_prototype.infra.db.engine import get_db
from agent_prototype.api.routes.dependencies import error_response

router = APIRouter(prefix="/settings")


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

@router.post("/providers", response_model=ProviderOut, status_code=status.HTTP_201_CREATED)
def create_provider_api(payload: CreateProviderInput, db: Session = Depends(get_db)) -> ProviderOut:
    service = SettingsService(db)
    return service.create_provider(
        name=payload.name,
        base_url=payload.base_url,
        api_key=payload.api_key,
    )


@router.get("/providers", response_model=list[ProviderOut])
def list_providers_api(db: Session = Depends(get_db)) -> list[ProviderOut]:
    service = SettingsService(db)
    return service.list_providers()


@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider_api(provider_id: int, db: Session = Depends(get_db)) -> None:
    try:
        service = SettingsService(db)
        service.delete_provider(provider_id)
    except ValueError as exc:
        return error_response(status.HTTP_404_NOT_FOUND, "provider_not_found", str(exc))


@router.patch("/providers/{provider_id}", response_model=ProviderOut)
def patch_provider_api(provider_id: int, payload: PatchProviderInput, db: Session = Depends(get_db)) -> ProviderOut:
    try:
        service = SettingsService(db)
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
def sync_provider_models_api(provider_id: int, db: Session = Depends(get_db)) -> list[ModelOut]:
    try:
        service = SettingsService(db)
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
    db: Session = Depends(get_db),
) -> list[ModelOut]:
    service = SettingsService(db)
    return service.list_models(provider_id=provider_id, enabled_only=enabled is True)


@router.patch("/models/{model_id}", response_model=ModelOut)
def patch_model_api(model_id: int, payload: PatchModelInput, db: Session = Depends(get_db)) -> ModelOut:
    try:
        service = SettingsService(db)
        return service.patch_model(
            model_id,
            enabled=payload.enabled,
            display_name=payload.display_name,
        )
    except ValueError as exc:
        return error_response(status.HTTP_404_NOT_FOUND, "model_not_found", str(exc))