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

from agent_prototype.agent.settings.types import ModelOut, ProviderOut
from agent_prototype.api.dto.schemas import CreateProviderInput, PatchModelInput, PatchProviderInput
from agent_prototype.agent.settings import SettingsService
from agent_prototype.api.routes.dependencies import error_response, get_settings_service

router = APIRouter(prefix="/settings")


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


@router.post("/providers", response_model=ProviderOut, status_code=status.HTTP_201_CREATED)
def create_provider_api(
    payload: CreateProviderInput, service: SettingsService = Depends(get_settings_service)
) -> ProviderOut:
    """这个函数是用来创建一个新的大模型厂商（Provider）的。

    比如你想添加一个新的 OpenAI 兼容厂商或者本地的 Ollama 服务，你就需要把它的名字、接口地址和 API Key 传过来。

    需要拿到的东西：
    - payload: CreateProviderInput 对象，里面包含厂商的名字、API 地址（base_url）以及密钥（api_key）。
    - service: SettingsService 实例，由依赖注入提供。

    会给出来的结果：
    - ProviderOut 对象，也就是刚刚创建成功的模型厂商的详细信息（包含自动分配的厂商 ID 等）。
    """
    return service.create_provider(
        name=payload.name,
        base_url=payload.base_url,
        api_key=payload.api_key,
    )


@router.get("/providers", response_model=list[ProviderOut])
def list_providers_api(
    service: SettingsService = Depends(get_settings_service),
) -> list[ProviderOut]:
    """这个函数是用来列出系统里所有已配置的大模型厂商（Provider）的。

    方便你在设置界面上查看目前都有哪些大模型厂商可用。

    需要拿到的东西：
    - service: SettingsService 实例，由依赖注入提供。

    会给出来的结果：
    - 包含所有已配置厂商信息的列表（List[ProviderOut]）。
    """
    return service.list_providers()


@router.delete("/providers/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_provider_api(
    provider_id: int, service: SettingsService = Depends(get_settings_service)
) -> None:
    """这个函数是用来删除指定 ID 的大模型厂商的。

    如果某个厂商不用它了，可以通过这个接口删掉它。

    需要拿到的东西：
    - provider_id: 整数类型，也就是你要删除的大模型厂商的唯一 ID。
    - service: SettingsService 实例，由依赖注入提供。

    会给出来的结果：
    - 成功删除后没有返回值（统一返回 204 No Content）。如果找不到对应的厂商，会返回 404 错误。
    """
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
    """这个函数是用来修改或者更新某个大模型厂商的配置的。

    比如你修改了厂商的 API Key 或者 API 接口地址，甚至是要把它设为默认厂商，都可以调用这个接口。

    需要拿到的东西：
    - provider_id: 整数类型，代表你要修改的大模型厂商的 ID。
    - payload: PatchProviderInput 对象，里面有你要更新的名字、地址、密钥或是否设为默认等信息。
    - service: SettingsService 实例，由依赖注入提供。

    会给出来的结果：
    - ProviderOut 对象，修改成功后的厂商最新配置信息。
    """
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
    """这个函数是用来同步大模型厂商所拥有的具体模型列表的。

    它会去厂商那边打个招呼，把厂商支持的所有大语言模型（比如 gpt-4o, claude-3-5 等）拉下来存入我们的本地数据库。

    需要拿到的东西：
    - provider_id: 整数类型，你要同步的厂商 ID。
    - service: SettingsService 实例，由依赖注入提供。

    会给出来的结果：
    - 同步完成后的最新模型列表（List[ModelOut]）。
    """
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
    """这个函数是用来列出本地数据库中保存的所有可用模型的。

    你还可以选择只看某一个厂商的模型，或者只看启用了的模型。

    需要拿到的东西：
    - provider_id: 可选的整数，用来过滤特定厂商的模型。
    - enabled: 可选的布尔值，如果为 True 则只返回当前被启用的模型。
    - service: SettingsService 实例，由依赖注入提供。

    会给出来的结果：
    - 包含符合过滤条件的模型列表（List[ModelOut]）。
    """
    return service.list_models(provider_id=provider_id, enabled_only=enabled is True)


@router.patch("/models/{model_id}", response_model=ModelOut)
def patch_model_api(
    model_id: int,
    payload: PatchModelInput,
    service: SettingsService = Depends(get_settings_service),
) -> ModelOut:
    """这个函数是用来修改单个模型配置的。

    比如你想把某个模型禁用/启用，或者给它起一个好听的中文别名（显示名称），就可以调用这个接口。

    需要拿到的东西：
    - model_id: 整数类型，要修改的模型 ID。
    - payload: PatchModelInput 对象，里面有你要设置的是否启用状态或者展示名字。
    - service: SettingsService 实例，由依赖注入提供。

    会给出来的结果：
    - ModelOut 对象，修改成功后的模型最新配置信息。
    """
    try:
        return service.patch_model(
            model_id,
            enabled=payload.enabled,
            display_name=payload.display_name,
        )
    except ValueError as exc:
        return error_response(status.HTTP_404_NOT_FOUND, "model_not_found", str(exc))
