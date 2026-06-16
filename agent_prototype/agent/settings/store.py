"""配置仓储实现。

职责：
- 将模型供应商与模型配置持久化写入 SQLite 数据库。
- 提供数据库实体与领域传输模型（DTO）的互转。

上游：
- SettingsService

下游：
- SQLAlchemy / ORM (ProviderConfig, ModelSetting)

不负责：
- 不做 HTTP 请求路由与接口适配。
- 不做复杂业务规则验证。
"""

from agent_prototype.infra.db.orm_models import ProviderConfig, ModelSetting
from typing import Optional
from sqlalchemy.orm import Session


class SqliteSettingsStore:
    """SQLite 配置仓储，负责全局配置与模型的物理 CRUD 操作。"""

    def __init__(self, db: Session):
        """初始化仓储。"""
        self.db = db

    def create_provider(self, name: str, base_url: str, api_key: str) -> ProviderConfig:
        """登记或更新大模型厂商记录。"""
        record = (
            self.db.query(ProviderConfig)
            .filter(ProviderConfig.base_url == base_url)
            .first()
        )
        if record is not None:
            record.name = name
            record.api_key = api_key
            return record
        new_record = ProviderConfig(name=name, api_key=api_key, base_url=base_url)
        self.db.add(new_record)
        return new_record

    def list_providers(self) -> list[ProviderConfig]:
        """获取所有供应商记录，按创建时间降序排序。"""
        return (
            self.db.query(ProviderConfig)
            .order_by(ProviderConfig.created_at.desc())
            .all()
        )

    def patch_provider(
        self,
        provider_id: int,
        name: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        is_default: Optional[bool] = None,
    ) -> Optional[ProviderConfig]:
        """局部修改供应商配置。若设为默认，则清除其它记录的默认标记。"""
        record = (
            self.db.query(ProviderConfig)
            .filter(ProviderConfig.id == provider_id)
            .first()
        )
        if record is None:
            return None
        if name is not None:
            record.name = name
        if base_url is not None:
            record.base_url = base_url
        if api_key is not None:
            record.api_key = api_key
        if is_default is True:
            self.db.query(ProviderConfig).update({ProviderConfig.is_default: 0})
            record.is_default = 1
        return record

    def delete_provider(self, provider_id: int) -> None:
        """从数据库物理删除指定的供应商记录（级联删除关联模型配置）。"""
        record = (
            self.db.query(ProviderConfig)
            .filter(ProviderConfig.id == provider_id)
            .first()
        )
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
        """保存或更新从供应商同步的模型设置。若已存在则覆盖更新属性。"""
        record = (
            self.db.query(ModelSetting)
            .filter(
                ModelSetting.provider_id == provider_id,
                ModelSetting.model_id == model_id,
            )
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
        """查询模型列表，支持按供应商或启用状态过滤。"""
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
        """局部修改模型配置（是否启用或显示名称）。"""
        record = (
            self.db.query(ModelSetting).filter(ModelSetting.id == model_db_id).first()
        )
        if record is None:
            return None
        if enabled is not None:
            record.enabled = enabled
        if display_name is not None:
            record.display_name = display_name
        return record
