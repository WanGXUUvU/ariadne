"""应用服务层 (Application Layer) - 全局配置服务

职责：
1. 编排全局系统配置（API Key, 模型配置参数等）读取和保存的业务用例。
2. 对设置项的有效性进行业务层规则校验。

不负责：
1. 配置项在 SQLite 数据库中的物理 CRUD。
2. HTTP 协议转换和接口路由。

数据流向：
- 输入：配置修改属性字典。
- 输出：修改后的系统配置实体。
- 上游来源：agent_prototype/api/routes/settings_routes.py。
- 下游流向：调用 agent_prototype/agent/settings/store.py 进行数据持久化。
"""

import json
import re
from typing import Optional
import requests
from sqlalchemy.orm import Session

from agent_prototype.core.types import ModelOut, ProviderOut
from agent_prototype.prompt.strategies.thinking import get_effort_levels
from agent_prototype.infra.db.orm_models import ProviderConfig, ModelSetting
from agent_prototype.agent.settings.store import SqliteSettingsStore


class SettingsService:
    """这个类是管理大模型厂商（Provider）和具体大语言模型（Model）配置的服务大管家（业务逻辑层）。
    
    它负责统筹厂商的注册、删除、修改，以及连接外置 API 接口去实时同步该厂商所拥有的各种模型。它还会根据模型的名字智能推断出这个模型具备什么特征（比如是否支持深度思考、支持哪些思考级别、是不是支持工具等）。
    
    它的上下游：
    - 上游：API 路由层 settings_routes.py。
    - 下游：底层配置仓储层 store.py。
    """
    
    def __init__(self, db: Session):
        """大管家初始化函数，将数据库会话保存起来并创建对应的底层设置保险箱。
        
        需要拿到的东西：
        - db: 数据库连接会话，用来与数据库进行读写交互。
        
        会给出来的结果：
        - 服务类实例本身。
        """
        self.db = db
        self.store = SqliteSettingsStore(db)

    def _provider_to_out(self, record: ProviderConfig) -> ProviderOut:
        """这是一个内部转换的小助手，负责把数据库底层的老实人实体 ProviderConfig 转换成面向前端的标准数据包 ProviderOut。
        
        在这个过程中，它还会贴心地把敏感的 API Key 进行打码脱敏（比如 OpenAI Key 变成只留后四位的 ****4567 这种暗示字符串），防止密钥在前端泄露。
        
        需要拿到的东西：
        - record: 数据库厂商记录实体。
        
        会给出来的结果：
        - ProviderOut 脱敏后的厂商数据包。
        """
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
        """这是一个内部转换的小助手，负责把数据库里存的模型实体 ModelSetting 转换成面向前端的标准数据包 ModelOut。
        
        需要拿到的东西：
        - record: 数据库模型配置记录实体。
        
        会给出来的结果：
        - ModelOut 格式的模型数据包。
        """
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
        """向系统里添加配置一个新的大模型厂商。
        
        需要拿到的东西：
        - name: 字符串，给这个厂商起个名字（比如 'DeepSeek'）。
        - base_url: 字符串，该厂商的 API 接口基地址（如 'https://api.deepseek.com/v1'）。
        - api_key: 字符串，你在这个厂商申请的 API 密钥。
        
        会给出来的结果：
        - 添加成功后，会把这个厂商脱敏后的配置信息返回给你。
        """
        record = self.store.create_provider(name=name, base_url=base_url, api_key=api_key)
        self.db.commit()
        self.db.refresh(record)
        return self._provider_to_out(record)

    def list_providers(self) -> list[ProviderOut]:
        """获取当前系统里所有已经配置好、登记在册的大模型厂商列表。
        
        需要拿到的东西：
        - 无需额外参数。
        
        会给出来的结果：
        - 包含所有登记在册的脱敏厂商配置列表（List[ProviderOut]）。
        """
        return [self._provider_to_out(r) for r in self.store.list_providers()]

    def patch_provider(
        self,
        provider_id: int,
        name: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        is_default: Optional[bool] = None
    ) -> ProviderOut:
        """局部修改或者更新某个已注册大模型厂商的参数。
        
        比如你换了新 API Key，或者换了新的接口地址，或者想把它设置为系统默认的厂商。
        
        需要拿到的东西：
        - provider_id: 整数，要修改的那个厂商的唯一数据库 ID。
        - name: 可选字符串，新的厂商名字。
        - base_url: 可选字符串，新的接口基地址。
        - api_key: 可选字符串，新的 API 密钥。
        - is_default: 可选布尔值，是否设为系统默认厂商。
        
        会给出来的结果：
        - 更新成功后的最新脱敏厂商配置信息。如果找不到对应 ID 的厂商，会报错。
        """
        record = self.store.patch_provider(
            provider_id, name=name, base_url=base_url, api_key=api_key, is_default=is_default
        )
        if record is None:
            raise ValueError(f"Provider {provider_id} not found")
        self.db.commit()
        self.db.refresh(record)
        return self._provider_to_out(record)

    def delete_provider(self, provider_id: int) -> None:
        """把指定的模型厂商彻底从系统里删掉。
        
        级联效应是，这个厂商下同步下来的所有具体模型列表也会被一并清理干净。
        
        需要拿到的东西：
        - provider_id: 整数，你要删掉的厂商 ID。
        
        会给出来的结果：
        - 无返回值（执行成功后将删除数据库里的对应记录）。
        """
        self.store.delete_provider(provider_id)
        self.db.commit()

    def list_models(self, provider_id: Optional[int] = None, enabled_only: bool = False) -> list[ModelOut]:
        """列出系统当前保存的所有具体模型列表。
        
        支持各种筛选，比如只看某一个厂商的模型，或者只看当前处于"启用"状态可以供用户选择聊天的模型。
        
        需要拿到的东西：
        - provider_id: 可选的整数，如果传了就只返回该厂商旗下的模型。
        - enabled_only: 布尔值，如果为 True 则只捞出处于启用状态的模型。
        
        会给出来的结果：
        - 符合过滤要求的模型列表（List[ModelOut]）。
        """
        return [self._model_to_out(r) for r in self.store.list_models(provider_id=provider_id, enabled_only=enabled_only)]

    def patch_model(self, model_db_id: int, enabled: Optional[bool] = None, display_name: Optional[str] = None) -> ModelOut:
        """修改某个具体模型的别名（展示名称）或者切换启用/禁用状态。
        
        例如你想把某个不好记的模型名字改得更接地气，或者暂时禁用某个很贵的模型。
        
        需要拿到的东西：
        - model_db_id: 整数，数据库中该模型记录的 ID。
        - enabled: 可选布尔值，是否启用该模型。
        - display_name: 可选字符串，该模型的新别名。
        
        会给出来的结果：
        - 修改成功后的最新模型配置信息。如果找不到该模型记录，会报错。
        """
        enabled_int = int(enabled) if enabled is not None else None
        record = self.store.patch_model(model_db_id, enabled=enabled_int, display_name=display_name)
        if record is None:
            raise ValueError(f"ModelSetting {model_db_id} not found")
        self.db.commit()
        self.db.refresh(record)
        return self._model_to_out(record)

    def infer_thinking_style(self, model_id: str, supported_features: list[str]) -> str:
        """这是一个神奇的推断小助手。
        
        它通过模型的 ID 关键字和支持的特征列表，智能化地猜出这个模型在"深度思考（Thinking/Reasoning）"时的流派风格。
        
        需要拿到的东西：
        - model_id: 字符串，模型的官方 ID（例如 'deepseek-reasoner'）。
        - supported_features: 字符串列表，该模型支持的特征（比如 'reasoning', 'tools' 等）。
        
        会给出来的结果：
        - 推断出来的深度思考风格类型（字符串，比如 'deepseek_style', 'kimi_style', 'none' 等）。
        """
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
        """请求外置提供商模型字典，自适应识别并物理同步到本地数据库中。
        
        它会自动过滤掉不能处理文本的纯图像模型。
        
        需要拿到的东西：
        - provider_id: 整数，要同步的那个厂商的 ID。
        
        会给出来的结果：
        - 同步入库成功后的最新模型列表（List[ModelOut]）。
        """
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
