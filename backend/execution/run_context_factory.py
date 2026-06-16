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
- SessionStore
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

from backend.agent.definition import AgentDefinitionService
from backend.context.assembler import ContextAssembler
from backend.context.compaction import HistoryCompactor
from backend.core.adapters.chat_completions import ChatCompletionsAdapter
from backend.execution.persistence.types import RunInput, RunContext
from backend.execution.runtime.types import RunState
from backend.infra.db.orm_models import (
    ModelSetting,
    ProviderConfig,
    SessionRecord,
)
from backend.memory.session.store import SessionStore
from backend.memory.summary.service import CompactService
from backend.prompt.builder import (
    build_runtime_system_prompt,
    build_skill_catalog_prompt,
)
from backend.prompt.strategies.thinking import build_thinking_payload
from backend.security.policy.types import PROFILES


class RunContextFactory:
    """负责为一次运行准备完整的运行物料。"""

    def __init__(self, db: Session):
        self.db = db
        self.store = SessionStore(db)

    def assemble(self, run_input: RunInput) -> RunContext:
        """构建一次运行所需的完整上下文。

        这一步的产物就是 RunContext。它是 run 开始前最关键的稳定背景物料，
        后面的 RunService / RunLifecycle / AgentRunner 都默认依赖它。
        """
        session_id = run_input.session_id
        record = self._load_record(session_id)
        # 先根据 session 绑定的 provider/model 准备好模型适配器。
        adapter = self._create_adapter(session_id, record)
        # 读取 session 最新状态快照，作为本轮运行起点。
        state = self.store.get(session_id) or RunState()

        context_tokens = (
            record.context_tokens if record and record.context_tokens else 0
        )
        session_type = record.session_type if record else "assistant"
        workspace_path = record.workspace_path if record else None

        context_length = self._resolve_context_length(record, context_tokens)

        if state.messages:
            # 在真正进入 run 前，先按当前模型上下文长度预算执行一次自动压缩。
            compactor = HistoryCompactor(adapter)
            compact_result = CompactService(self.db).auto_compact_in_memory(
                state=state,
                context_tokens=context_tokens,
                context_length=context_length,
                compactor=compactor,
            )
            state = compact_result.state

        effective_agent_name = self._resolve_effective_agent_name(
            run_input, session_type
        )
        definition = AgentDefinitionService(self.db).load_definition(
            effective_agent_name
        )

        assembler = ContextAssembler(
            self.db,
            build_skill_catalog_prompt=build_skill_catalog_prompt,
            build_runtime_system_prompt=build_runtime_system_prompt,
        )
        assembled_ctx = assembler.assemble(
            run_input=run_input,
            session_type=session_type,
            workspace_path=workspace_path,
            definition=definition,
        )
        runtime_definition = definition.model_copy(
            update={"system_prompt": assembled_ctx.system_prompt}
        )

        approval_policy = self._resolve_approval_policy(record)

        # 最终产出的 RunContext 是“这一轮已经准备好可以直接执行”的稳定运行背景。
        return RunContext(
            state=state,
            agent_profile=runtime_definition,
            adapter=adapter,
            approval_policy=approval_policy,
            effective_agent_name=effective_agent_name,
            workspace_path=workspace_path,
            session_type=session_type,
        )

    def create_adapter(self, session_id: str) -> ChatCompletionsAdapter:
        """为恢复运行等场景单独构建模型适配器。"""
        return self._create_adapter(session_id)

    def _load_record(self, session_id: str) -> Optional[SessionRecord]:
        """读取 session 主记录。"""
        return (
            self.db.query(SessionRecord)
            .filter(SessionRecord.session_id == session_id)
            .first()
        )

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
        run_input: RunInput,
        session_type: str,
    ) -> str:
        """解析本轮实际使用的 agent 名称。"""
        if session_type == "coding":
            return "software_engineer"
        return run_input.agent_name or "default"

    def _resolve_approval_policy(self, record: Optional[SessionRecord]):
        """根据 session 权限档位选择审批策略。"""
        profile_name = (
            record.permission_profile
            if record and record.permission_profile
            else "conservative"
        )
        return PROFILES.get(profile_name, PROFILES["conservative"]).approval_policy

    def _create_adapter(
        self,
        session_id: str,
        record: Optional[SessionRecord] = None,
    ) -> ChatCompletionsAdapter:
        """根据 session 绑定的 provider/model 配置构建模型适配器。"""
        if record is None:
            record = self._load_record(session_id)

        if (
            record is None
            or record.model_provider_id is None
            or record.model_id is None
        ):
            raise ValueError(
                "当前会话未配置模型，请在设置中选择 Provider 和模型后再开始对话"
            )

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
