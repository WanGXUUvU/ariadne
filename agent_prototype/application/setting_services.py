import json
import re
from typing import Optional

import requests
from sqlalchemy.orm import Session

from ..core.schemas import ModelOut, ProviderOut
from ..model.thinking_styles import get_effort_levels
from ..storage.models import ProviderConfig, ModelSetting
from ..storage.stores.settings_store import SqliteSettingStore


# ---------------------------------------------------------------------------
# 内部转换工具
# ---------------------------------------------------------------------------

def _provider_to_out(record: ProviderConfig) -> ProviderOut:
    key = record.api_key or ""
    hint = ("****" + key[-4:]) if len(key) >= 4 else ("*" * len(key)) if key else None
    return ProviderOut(
        id=record.id,
        name=record.name,
        base_url=record.base_url,
        api_key_hint=hint,
        created_at=record.created_at,
        is_default=bool(record.is_default),
    )


def _model_to_out(record: ModelSetting) -> ModelOut:
    return ModelOut(
        id=record.id,
        provider_id=record.provider_id,
        model_id=record.model_id,
        display_name=record.display_name,
        enabled=bool(record.enabled),
        supports_thinking=bool(record.supports_thinking),
        thinking_style=record.thinking_style,
        effort_levels=json.loads(record.effort_levels or "[]"),
        context_length=record.context_length,
        supports_tools=bool(record.supports_tools),
    )


# ---------------------------------------------------------------------------
# Provider CRUD
# ---------------------------------------------------------------------------

def create_provider_service(name: str, base_url: str, api_key: str, db: Session) -> ProviderOut:
    """新建或更新 provider（按 base_url 去重），提交事务后返回。"""
    store = SqliteSettingStore(db)
    record = store.create_provider(name=name, base_url=base_url, api_key=api_key)
    db.commit()
    db.refresh(record)
    return _provider_to_out(record)


def list_providers_service(db: Session) -> list[ProviderOut]:
    store = SqliteSettingStore(db)
    return [_provider_to_out(r) for r in store.list_providers()]


def patch_provider_service(
    provider_id: int,
    db: Session,
    name: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    is_default:Optional[bool]=None
) -> ProviderOut:
    """按 id 更新 provider，至少传一个字段。"""
    store = SqliteSettingStore(db)
    record = store.patch_provider(provider_id, name=name, base_url=base_url, api_key=api_key,is_default=is_default)
    if record is None:
        raise ValueError(f"Provider {provider_id} not found")
    db.commit()
    db.refresh(record)
    return _provider_to_out(record)


def delete_provider_service(provider_id: int, db: Session) -> None:
    """删除 provider 及其所有 model_settings（CASCADE）。"""
    store = SqliteSettingStore(db)
    store.delete_provider(provider_id)
    db.commit()


# ---------------------------------------------------------------------------
# Model CRUD
# ---------------------------------------------------------------------------

def list_models_service(
    db: Session,
    provider_id: Optional[int] = None,
    enabled_only: bool = False,
) -> list[ModelOut]:
    store = SqliteSettingStore(db)
    return [_model_to_out(r) for r in store.list_models(provider_id=provider_id, enabled_only=enabled_only)]


def patch_model_service(
    model_db_id: int,
    db: Session,
    enabled: Optional[bool] = None,
    display_name: Optional[str] = None,
) -> ModelOut:
    """更新模型的 enabled 或 display_name，至少传一个。"""
    store = SqliteSettingStore(db)
    enabled_int = int(enabled) if enabled is not None else None
    record = store.patch_model(model_db_id, enabled=enabled_int, display_name=display_name)
    if record is None:
        raise ValueError(f"ModelSetting {model_db_id} not found")
    db.commit()
    db.refresh(record)
    return _model_to_out(record)


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

def infer_thinking_style(model_id: str, supported_features: list[str]) -> str:
    """根据 model_id 关键字和 supported_features 推断 thinking style。纯函数，不访问 DB。
    
    优先读 supported_features，再通过模型名兜底（部分厂商不返回 reasoning 字段）。
    返回 "none" 表示该模型不支持思考。
    """
    m = model_id.lower()
    has_reasoning = "reasoning" in supported_features

    # ── 通过 supported_features 明确声明的推理模型 ──
    if has_reasoning:
        if "deepseek" in m:
            return "deepseek_style"
        if "moonshot" in m or "kimi" in m:
            return "kimi_style"
        if "glm" in m or "z1" in m:
            return "glm_style"
        return "sensenova_style"

    # ── 兜底：通过模型名推断（适配未声明 supported_features 的厂商）──
    # Claude：haiku 系列不支持 extended thinking，其余 sonnet/opus 均支持
    if "claude" in m and "haiku" not in m:
        return "claude_style"
    # DeepSeek 全系列（V4/R1/R2/R3 等）统一使用双字段格式
    if "deepseek" in m:
        return "deepseek_style"
    # Qwen3 / QwQ 系列：enable_thinking 顶层参数
    if "qwq" in m or "qwen3" in m:
        return "qwen_style"
    # Kimi K 系列（K1.5 / K2.x 均为推理模型）
    if ("kimi" in m or "moonshot" in m) and "-k" in m:
        return "kimi_style"
    # OpenAI o 系列推理模型（reasoning_effort 顶层参数）
    if "openai-o" in m or re.match(r"^o\d", m):
        return "deepseek_style"
    # OpenAI gpt-5.1+ 系列支持 xhigh 档位（5.1-codex-max, 5.2, 5.3-codex, 5.4, 5.5 等）
    if re.match(r"openai-gpt-5\.[1-9]", m):
        return "openai_style"
    # OpenAI gpt-5（基础版）/ gpt-5-mini / gpt-5-nano：仅 low/medium/high
    if re.match(r"openai-gpt-[5-9]", m):
        return "deepseek_style"
    # MiniMax-M2 及以上系列：thinking 训练进去，响应中以 <think> 标签包裹，无 API 参数控制
    if "minimax" in m and re.search(r"m[2-9]", m):
        return "always_on_style"
    # 名字里带 "thinking" 的模型（如 arcee-trinity-large-thinking）
    # 这类模型 thinking 是训练进去的，无 API 参数可控，不发任何 payload
    # if "thinking" in m: return "none"  ← 不能当作 sensenova_style，直接跳过

    return "none"


def sync_provider_models_service(provider_id: int, db: Session) -> list[ModelOut]:
    """从 provider 的 /models 接口同步模型列表到数据库，返回本次同步的模型列表。"""
    store = SqliteSettingStore(db)

    provider = db.query(ProviderConfig).filter(ProviderConfig.id == provider_id).first()
    if provider is None:
        raise ValueError(f"Provider {provider_id} not found")

    resp = requests.get(
        f"{provider.base_url.rstrip('/')}/models",
        headers={"Authorization": f"Bearer {provider.api_key}"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json().get("data", [])

    results = []
    for item in data:
        model_id = item.get("id", "")
        output_modalities = item.get("output_modalities") or []
        if "image" in output_modalities:
            continue

        supported_features = item.get("supported_features") or []
        thinking_style = infer_thinking_style(model_id, supported_features)
        supports_thinking = thinking_style != "none"

        record = store.upsert_model(
            provider_id=provider_id,
            model_id=model_id,
            display_name=item.get("display_name") or model_id,
            supports_thinking=supports_thinking,
            thinking_style=thinking_style,
            effort_levels=json.dumps(get_effort_levels(thinking_style)),
            context_length=item.get("context_length"),
            supports_tools="tools" in supported_features,
        )
        results.append(record)

    db.commit()
    return [_model_to_out(r) for r in results]

