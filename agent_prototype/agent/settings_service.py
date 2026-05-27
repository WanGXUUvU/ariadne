import json
import re
from typing import Optional
import requests
from sqlalchemy.orm import Session

from agent_prototype.api.dto.schemas import ModelOut, ProviderOut
from agent_prototype.prompt.strategies.thinking import get_effort_levels
from agent_prototype.infra.db.orm_models import ProviderConfig, ModelSetting
from agent_prototype.agent.settings_store import SqliteSettingsStore


class SettingsService:
    """提供商与模型字典管理服务类 (OOP)
    
    职责：
    1. 负责管理 API 提供商配置的创建、列表输出、打补丁更新及物理删除；
    2. 从提供商侧的 `/models` 接口拉取并物理同步模型信息，根据模型命名自适应推断其推理特征。
    """
    
    def __init__(self, db: Session):
        """注入 db 会话并聚合 SqliteSettingStore 仓储"""
        self.db = db
        self.store = SqliteSettingsStore(db)

    def _provider_to_out(self, record: ProviderConfig) -> ProviderOut:
        """内部转换：将数据库 PO 转换为 DTO Out Schema"""
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

    def _model_to_out(self, record: ModelSetting) -> ModelOut:
        """内部转换：将数据库 Model 记录转换为 DTO ModelOut Schema"""
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

    def create_provider(self, name: str, base_url: str, api_key: str) -> ProviderOut:
        """创建或修改 API 提供商"""
        record = self.store.create_provider(name=name, base_url=base_url, api_key=api_key)
        self.db.commit()
        self.db.refresh(record)
        return self._provider_to_out(record)

    def list_providers(self) -> list[ProviderOut]:
        """获取所有已注册提供商"""
        return [self._provider_to_out(r) for r in self.store.list_providers()]

    def patch_provider(
        self,
        provider_id: int,
        name: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        is_default: Optional[bool] = None
    ) -> ProviderOut:
        """局部修改提供商参数"""
        record = self.store.patch_provider(
            provider_id, name=name, base_url=base_url, api_key=api_key, is_default=is_default
        )
        if record is None:
            raise ValueError(f"Provider {provider_id} not found")
        self.db.commit()
        self.db.refresh(record)
        return self._provider_to_out(record)

    def delete_provider(self, provider_id: int) -> None:
        """删除提供商（下级关联模型会联级物理删除）"""
        self.store.delete_provider(provider_id)
        self.db.commit()

    def list_models(self, provider_id: Optional[int] = None, enabled_only: bool = False) -> list[ModelOut]:
        """列出模型列表，支持按提供商筛选"""
        return [self._model_to_out(r) for r in self.store.list_models(provider_id=provider_id, enabled_only=enabled_only)]

    def patch_model(self, model_db_id: int, enabled: Optional[bool] = None, display_name: Optional[str] = None) -> ModelOut:
        """修改模型的别名或启用状态"""
        enabled_int = int(enabled) if enabled is not None else None
        record = self.store.patch_model(model_db_id, enabled=enabled_int, display_name=display_name)
        if record is None:
            raise ValueError(f"ModelSetting {model_db_id} not found")
        self.db.commit()
        self.db.refresh(record)
        return self._model_to_out(record)

    def infer_thinking_style(self, model_id: str, supported_features: list[str]) -> str:
        """根据 model_id 关键字和 supported_features 推断思考风格"""
        m = model_id.lower()
        has_reasoning = "reasoning" in supported_features

        if has_reasoning:
            if "deepseek" in m:
                return "deepseek_style"
            if "moonshot" in m or "kimi" in m:
                return "kimi_style"
            if "glm" in m or "z1" in m:
                return "glm_style"
            return "sensenova_style"

        if "claude" in m and "haiku" not in m:
            return "claude_style"
        if "deepseek" in m:
            return "deepseek_style"
        if "qwq" in m or "qwen3" in m:
            return "qwen_style"
        if ("kimi" in m or "moonshot" in m) and "-k" in m:
            return "kimi_style"
        if "openai-o" in m or re.match(r"^o\d", m):
            return "deepseek_style"
        if re.match(r"openai-gpt-5\.[1-9]", m):
            return "openai_style"
        if re.match(r"openai-gpt-[5-9]", m):
            return "deepseek_style"
        if "minimax" in m and re.search(r"m[2-9]", m):
            return "always_on_style"

        return "none"

    def sync_provider_models(self, provider_id: int) -> list[ModelOut]:
        """请求外置提供商模型字典，自适应识别并物理同步到本地数据库中"""
        provider = self.db.query(ProviderConfig).filter(ProviderConfig.id == provider_id).first()
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
            thinking_style = self.infer_thinking_style(model_id, supported_features)
            supports_thinking = thinking_style != "none"

            record = self.store.upsert_model(
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

        self.db.commit()
        return [self._model_to_out(r) for r in results]

