"""运行时上下文装配工厂。

职责：
- 读取 session 主记录和状态快照。
- 构建模型适配器并解析审批策略。
- 选择运行时 agent definition。
- 在进入 run 前评估并执行自动压缩。

上游：
- RunService
- ResumeRunService

下游：
- SqliteSessionStore
- AgentDefinitionService
- ContextAssembler
- CompactService

不负责：
- 不驱动 AgentRunner 执行。
- 不落库。
- 不查询 trace。
"""

from typing import Optional

from sqlalchemy.orm import Session

from agent_prototype.agent.definition import AgentDefinitionService
from agent_prototype.context.assembler import ContextAssembler
from agent_prototype.context.compaction import HistoryCompactor
from agent_prototype.core.adapters.chat_completions import ChatCompletionsAdapter
from agent_prototype.execution.persistence.types import AgentInput, RunContext
from agent_prototype.execution.runtime.types import AgentState
from agent_prototype.infra.db.orm_models import ModelSetting, ProviderConfig, SessionRecord
from agent_prototype.memory.session.store import SqliteSessionStore
from agent_prototype.memory.summary.service import CompactService
from agent_prototype.prompt.builder import (
    build_runtime_system_prompt,
    build_skill_catalog_prompt,
)
from agent_prototype.prompt.strategies.thinking import build_thinking_payload
from agent_prototype.security.policy.types import PROFILES


class RuntimeContextFactory:
    """负责为一次运行准备完整的运行物料。"""

    def __init__(self, db: Session):
        self.db = db
        self.store = SqliteSessionStore(db)

    def build(self, agent_input: AgentInput) -> RunContext:
        """构建一次运行所需的完整上下文。"""
        session_id = agent_input.session_id
        record = self._read_session_record(session_id)
        adapter = self._build_adapter(session_id, record)
        state = self.store.get(session_id) or AgentState()

        context_tokens = record.context_tokens if record and record.context_tokens else 0
        session_type = record.session_type if record else "assistant"
        workspace_path = record.workspace_path if record else None

        context_length = self._resolve_context_length(record, context_tokens)

        if state.messages:
            compactor = HistoryCompactor(adapter)
            compact_result = CompactService(self.db).auto_compact_in_memory(
                state=state,
                context_tokens=context_tokens,
                context_length=context_length,
                keep_recent_count=2,
                compactor=compactor,
            )
            state = compact_result.state

        effective_agent_name = self._resolve_effective_agent_name(agent_input, session_type)
        definition = AgentDefinitionService(self.db).load_definition(effective_agent_name)

        assembler = ContextAssembler(
            self.db,
            build_skill_catalog_prompt=build_skill_catalog_prompt,
            build_runtime_system_prompt=build_runtime_system_prompt,
        )
        assembled_ctx = assembler.assemble(
            agent_input=agent_input,
            session_type=session_type,
            workspace_path=workspace_path,
            definition=definition,
        )
        runtime_definition = definition.model_copy(
            update={"system_prompt": assembled_ctx.system_prompt}
        )

        approval_policy = self._resolve_approval_policy(record)

        return RunContext(
            state=state,
            definition=runtime_definition,
            adapter=adapter,
            approval_policy=approval_policy,
            effective_agent_name=effective_agent_name,
            workspace_path=workspace_path,
            session_type=session_type,
        )

    def build_adapter(self, session_id: str) -> ChatCompletionsAdapter:
        """为恢复运行等场景单独构建模型适配器。"""
        return self._build_adapter(session_id)

    def _read_session_record(self, session_id: str) -> Optional[SessionRecord]:
        """读取 session 主记录。"""
        return self.db.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()

    def _resolve_context_length(
        self,
        record: Optional[SessionRecord],
        fallback_tokens: int,
    ) -> int:
        """解析本次运行的上下文长度。"""
        model_setting = (
            self.db.query(ModelSetting)
            .filter(
                ModelSetting.model_id == record.model_id,
                ModelSetting.provider_id == record.model_provider_id,
            )
            .first()
            if record and record.model_id and record.model_provider_id
            else None
        )
        if model_setting and model_setting.context_length:
            return model_setting.context_length
        return fallback_tokens

    def _resolve_effective_agent_name(
        self,
        agent_input: AgentInput,
        session_type: str,
    ) -> str:
        """解析本轮实际使用的 agent 名称。"""
        if session_type == "coding":
            return "software_engineer"
        return agent_input.agent_name or "default"

    def _resolve_approval_policy(self, record: Optional[SessionRecord]):
        """根据 session 权限档位选择审批策略。"""
        profile_name = (
            record.permission_profile if record and record.permission_profile else "conservative"
        )
        return PROFILES.get(profile_name, PROFILES["conservative"]).approval_policy

    def _build_adapter(
        self,
        session_id: str,
        record: Optional[SessionRecord] = None,
    ) -> ChatCompletionsAdapter:
        """根据 session 绑定的 provider/model 配置构建模型适配器。"""
        if record is None:
            record = self._read_session_record(session_id)

        if record is None or record.model_provider_id is None or record.model_id is None:
            raise ValueError("当前会话未配置模型，请在设置中选择 Provider 和模型后再开始对话")

        provider = (
            self.db.query(ProviderConfig)
            .filter(ProviderConfig.id == record.model_provider_id)
            .first()
        )
        if provider is None:
            raise ValueError("会话关联的 Provider 已被删除，请重新选择模型")

        model_setting = (
            self.db.query(ModelSetting)
            .filter(
                ModelSetting.model_id == record.model_id,
                ModelSetting.provider_id == record.model_provider_id,
            )
            .first()
        )
        thinking_payload = build_thinking_payload(
            style=model_setting.thinking_style if model_setting else "none",
            enabled=bool(record.thinking_enabled),
            effort=record.thinking_effort or "medium",
        )
        return ChatCompletionsAdapter(
            api_key=provider.api_key,
            base_url=provider.base_url,
            model=record.model_id,
            extra_payload=thinking_payload,
        )
