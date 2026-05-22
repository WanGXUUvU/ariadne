from typing import Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ...core.schemas import CreateProviderInput, ModelOut, PatchModelInput, PatchProviderInput, ProviderOut
from ...application.setting_services import (
    create_provider_service,
    delete_provider_service,
    list_models_service,
    list_providers_service,
    patch_model_service,
    patch_provider_service,
    sync_provider_models_service,
)
from ...storage.db import get_db
from .common import error_response

router = APIRouter(prefix="/settings")


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

@router.post("/providers", response_model=ProviderOut, status_code=status.HTTP_201_CREATED)
def create_provider_api(payload: CreateProviderInput, db: Session = Depends(get_db)) -> ProviderOut:
    return create_provider_service(
        name=payload.name,
        base_url=payload.base_url,
        api_key=payload.api_key,
        db=db,
    )


@router.get("/providers", response_model=list[ProviderOut])
def list_providers_api(db: Session = Depends(get_db)) -> list[ProviderOut]:
    return list_providers_service(db)


@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider_api(provider_id: int, db: Session = Depends(get_db)) -> None:
    try:
        delete_provider_service(provider_id, db)
    except ValueError as exc:
        return error_response(status.HTTP_404_NOT_FOUND, "provider_not_found", str(exc))


@router.patch("/providers/{provider_id}", response_model=ProviderOut)
def patch_provider_api(provider_id: int, payload: PatchProviderInput, db: Session = Depends(get_db)) -> ProviderOut:
    try:
        return patch_provider_service(
            provider_id,
            db,
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
    """拉取并同步该 provider 的模型列表，写入 model_settings 后返回。"""
    try:
        return sync_provider_models_service(provider_id, db)
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
    return list_models_service(db, provider_id=provider_id, enabled_only=enabled is True)


@router.patch("/models/{model_id}", response_model=ModelOut)
def patch_model_api(model_id: int, payload: PatchModelInput, db: Session = Depends(get_db)) -> ModelOut:
    try:
        return patch_model_service(
            model_id,
            db,
            enabled=payload.enabled,
            display_name=payload.display_name,
        )
    except ValueError as exc:
        return error_response(status.HTTP_404_NOT_FOUND, "model_not_found", str(exc))
