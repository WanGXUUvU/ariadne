from ..models import ProviderConfig, ModelSetting
from typing import Optional
from sqlalchemy.orm import Session


class SqliteSettingsStore:
    def __init__(self, db: Session):
        self.db = db

    def create_provider(self, name: str, base_url: str, api_key: str) -> ProviderConfig:
        """有相同 base_url 则更新，否则新建。"""
        record = self.db.query(ProviderConfig).filter(ProviderConfig.base_url == base_url).first()
        if record is not None:
            record.name = name
            record.api_key = api_key
            return record
        new_record = ProviderConfig(name=name, api_key=api_key, base_url=base_url)
        self.db.add(new_record)
        return new_record

    def list_providers(self) -> list[ProviderConfig]:
        return self.db.query(ProviderConfig).order_by(ProviderConfig.created_at.desc()).all()

    def patch_provider(
        self,
        provider_id: int,
        name: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        is_default :Optional[bool]=None
    ) -> Optional[ProviderConfig]:
        """按 id 更新 provider 字段，至少传一个，返回更新后的记录或 None（未找到）。"""
        record = self.db.query(ProviderConfig).filter(ProviderConfig.id == provider_id).first()
        if record is None:
            return None
        if name is not None:
            record.name = name
        if base_url is not None:
            record.base_url = base_url
        if api_key is not None:
            record.api_key = api_key
        if is_default is True:
            self.db.query(ProviderConfig).update({ProviderConfig.is_default:0})
            record.is_default=1
        return record

    def delete_provider(self, provider_id: int) -> None:
        """删除 provider，model_settings 通过 CASCADE 自动删除。"""
        record = self.db.query(ProviderConfig).filter(ProviderConfig.id == provider_id).first()
        if record is not None:
            self.db.delete(record)

    def upsert_model(
        self,
        provider_id: int,
        model_id: str,
        display_name: str,
        supports_thinking: bool,
        thinking_style: str,
        effort_levels: str,
        context_length: Optional[int],
        supports_tools: bool,
    ) -> ModelSetting:
        """有则更新字段，无则插入新行（按 provider_id + model_id 联合查）。"""
        record = (
            self.db.query(ModelSetting)
            .filter(ModelSetting.provider_id == provider_id, ModelSetting.model_id == model_id)
            .first()
        )
        if record is not None:
            record.display_name = display_name
            record.supports_thinking = int(supports_thinking)
            record.thinking_style = thinking_style
            record.effort_levels = effort_levels
            record.context_length = context_length
            record.supports_tools = int(supports_tools)
            return record
        new_record = ModelSetting(
            provider_id=provider_id,
            model_id=model_id,
            display_name=display_name,
            supports_thinking=int(supports_thinking),
            thinking_style=thinking_style,
            effort_levels=effort_levels,
            context_length=context_length,
            supports_tools=int(supports_tools),
        )
        self.db.add(new_record)
        return new_record

    def list_models(
        self,
        provider_id: Optional[int] = None,
        enabled_only: bool = False,
    ) -> list[ModelSetting]:
        """查模型列表，可按 provider 或只看 enabled=1 的。"""
        query = self.db.query(ModelSetting)
        if provider_id is not None:
            query = query.filter(ModelSetting.provider_id == provider_id)
        if enabled_only:
            query = query.filter(ModelSetting.enabled == 1)
        return query.order_by(ModelSetting.id).all()

    def patch_model(
        self,
        model_db_id: int,
        enabled: Optional[int] = None,
        display_name: Optional[str] = None,
    ) -> Optional[ModelSetting]:
        """更新单个模型的 enabled 或 display_name。"""
        record = self.db.query(ModelSetting).filter(ModelSetting.id == model_db_id).first()
        if record is None:
            return None
        if enabled is not None:
            record.enabled = enabled
        if display_name is not None:
            record.display_name = display_name
        return record

