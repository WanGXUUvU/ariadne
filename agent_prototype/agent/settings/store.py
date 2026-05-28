"""应用服务层 (Application Layer) - 配置仓储层

职责：
1. 将系统配置记录持久化写入 SQLite 数据库。
2. 提供数据库表记录到业务配置对象的序列化与反序列化转换。

不负责：
1. 具体的路由接口配置或 HTTP 网关。
2. 复杂的配置业务合法性校验。

数据流向：
- 输入：数据库实体数据或配置查询参数。
- 输出：持久化后的配置模型。
- 上游来源：agent_prototype/agent/settings/service.py。
- 下游流向：调用 SQLAlchemy Session 提交到本地 SQLite 数据库。
"""

from agent_prototype.infra.db.orm_models import ProviderConfig, ModelSetting
from typing import Optional
from sqlalchemy.orm import Session


class SqliteSettingsStore:
    """这个类是大模型厂商和模型配置的数据库底层保险箱（SQLite 仓储实现）。
    
    它唯一的职责就是老老实实执行各种 SQL 语句或 SQLAlchemy ORM 操作，把厂商的参数、API 地址、API Key 以及各个同步出来的具体模型数据，稳稳当当地存入数据库表或者查询出来。
    
    它的上下游：
    - 上游：SettingsService 服务大管家。
    - 下游：数据库物理表 ORM 模型 ProviderConfig 和 ModelSetting。
    """
    def __init__(self, db: Session):
        """保险箱的初始化函数，把数据库连接会话存起来，方便后面随时进行存取。
        
        需要拿到的东西：
        - db: 数据库连接会话，用于执行 SQL 增删改查。
        
        会给出来的结果：
        - 仓储类实例本身。
        """
        self.db = db

    def create_provider(self, name: str, base_url: str, api_key: str) -> ProviderConfig:
        """在数据库中登记创建一个大模型厂商记录。
        
        如果数据库里已经有相同 API 接口地址（base_url）的厂商了，它会很聪明地直接在这个已有厂商上更新它的名字和 API 密钥；如果没有，就新建一条记录存进去。
        
        需要拿到的东西：
        - name: 字符串，厂商的名字。
        - base_url: 字符串，该厂商的接口基地址。
        - api_key: 字符串，你申请的 API 密钥。
        
        会给出来的结果：
        - 写入或者更新后的数据库厂商实体记录 ProviderConfig。
        """
        record = self.db.query(ProviderConfig).filter(ProviderConfig.base_url == base_url).first()
        if record is not None:
            record.name = name
            record.api_key = api_key
            return record
        new_record = ProviderConfig(name=name, api_key=api_key, base_url=base_url)
        self.db.add(new_record)
        return new_record

    def list_providers(self) -> list[ProviderConfig]:
        """从数据库中把所有登记在册的大模型厂商记录全部捞出来，并按照创建时间倒序（最新创建的在最前面）排好队返回。
        
        需要拿到的东西：
        - 无需额外参数。
        
        会给出来的结果：
        - 包含数据库中所有厂商实体记录的列表（List[ProviderConfig]）。
        """
        return self.db.query(ProviderConfig).order_by(ProviderConfig.created_at.desc()).all()

    def patch_provider(
        self,
        provider_id: int,
        name: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        is_default :Optional[bool]=None
    ) -> Optional[ProviderConfig]:
        """局部更新数据库中某个厂商的配置字段（比如改名、改密钥、改地址，或者将其设为系统默认厂商）。
        
        如果将其设为默认厂商，它会贴心地把数据库中其他所有厂商的 is_default 标记全部清零，保证全局有且只有一个默认厂商。
        
        需要拿到的东西：
        - provider_id: 整数，要更新的厂商的唯一数据库 ID。
        - name: 可选字符串，更新后的厂商名字。
        - base_url: 可选字符串，更新后的基地址。
        - api_key: 可选字符串，更新后的 API 密钥。
        - is_default: 可选布尔值，是否设为系统默认厂商。
        
        会给出来的结果：
        - 更新成功后的厂商最新实体记录对象，要是找不到这个厂商则返回 None。
        """
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
        """从数据库中物理删除指定的厂商记录。
        
        由于数据库设置了外键级联删除（CASCADE），该厂商旗下的所有模型配置记录也会被自动一并物理删除。
        
        需要拿到的东西：
        - provider_id: 整数，你想干掉的那个厂商 ID。
        
        会给出来的结果：
        - 无返回值。
        """
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
        """在数据库里保存或更新同步下来的具体模型配置信息。
        
        如果这个厂商下已经存在了这个模型（根据联合唯一索引 provider_id + model_id 来判断），它就会把最新的显示名字、是否支持思考、思考风格、上下文长度等属性统统覆盖更新进去；如果是一个之前从没见过的新模型，就会往数据库表里插入一条新行。
        
        需要拿到的东西：
        - provider_id: 整数，该模型归属的厂商 ID。
        - model_id: 字符串，模型的官方 ID（例如 'gpt-4o'）。
        - display_name: 字符串，用于展示的名字。
        - supports_thinking: 布尔值，是否支持深度思考。
        - thinking_style: 字符串，思考风格流派。
        - effort_levels: 字符串，支持的深度思考强度的 JSON 串。
        - context_length: 可选整数，上下文的最大 Token 长度。
        - supports_tools: 布尔值，是否支持调用外部工具。
        
        会给出来的结果：
        - 更新或插入成功后的模型实体记录 ModelSetting。
        """
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
        """从数据库中查询已保存的具体模型列表。
        
        支持很多筛选条件，比如只看某一个特定厂商的模型，或者只看当前处于"启用（enabled=1）"状态的模型。
        
        需要拿到的东西：
        - provider_id: 可选的整数，用来过滤厂商。
        - enabled_only: 布尔值，如果为 True 则只捞出已被启用的模型。
        
        会给出来的结果：
        - 包含数据库中符合条件的模型实体记录列表（List[ModelSetting]）。
        """
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
        """局部修改数据库中单个模型的启用状态（enabled）或者别名（display_name）。
        
        需要拿到的东西：
        - model_db_id: 整数，该模型在数据库表里的唯一主键 ID。
        - enabled: 可选的整数（0 或 1），是否启用。
        - display_name: 可选字符串，展示用的新别名。
        
        会给出来的结果：
        - 更新成功后的模型实体记录对象，找不到对应的记录则返回 None。
        """
        record = self.db.query(ModelSetting).filter(ModelSetting.id == model_db_id).first()
        if record is None:
            return None
        if enabled is not None:
            record.enabled = enabled
        if display_name is not None:
            record.display_name = display_name
        return record
