"""Run 上下文构建器。

职责：
- 读取 session 状态、触发自动压缩
- 加载 Agent 定义 + Skill 上下文
- 组装 LLM Adapter
- 读取审批策略
上游：RunService 调用
下游：SqliteSessionStore、AgentDefinitionService、SkillContextService、CompactService
"""

from dataclasses import dataclass
from typing import Optional
from sqlalchemy.orm import Session

from agent_prototype.core.schemas import PROFILES
from agent_prototype.infrastructure.database.models import ModelSetting, ProviderConfig, SessionRecord
from agent_prototype.infrastructure.database.repositories.session_store import SqliteSessionStore
from agent_prototype.infrastructure.llm.chat_completions_adapter import ChatCompletionsAdapter
from agent_prototype.interface.dto.schemas import AgentInput, AgentState, ApprovalPolicy
from agent_prototype.core.agent_definition import AgentDefinition
from agent_prototype.application.services.agent_definition_service import AgentDefinitionService
from agent_prototype.application.services.compact_service import CompactService
from agent_prototype.application.services.skill_context_service import SkillContextService


@dataclass
class RunContext:
    """一次 run 所需的全部上下文。"""
    state: AgentState
    definition: AgentDefinition
    adapter: ChatCompletionsAdapter
    approval_policy: ApprovalPolicy
    effective_agent_name: str
    workspace_path:str
    session_type: str


class RunContextBuilder:
    """负责把一次 run 所需的所有上下文准备好，打包成 RunContext 交给 RunService。"""

    def __init__(self, db: Session):
        self.db = db
        self.store = SqliteSessionStore(db)

    def build_adapter(self, session_id: str) -> ChatCompletionsAdapter:
        """仅构建 LLM Adapter，供不需要完整 RunContext 的场景使用（如 resume）。"""
        return self._build_adapter(session_id)

    def build(self, agent_input: AgentInput) -> RunContext:
        """组装并返回完整的 RunContext。"""
        session_id = agent_input.session_id

        # ── 读取 session 记录 ─────────────────────────────────────────────────
        record = self.db.query(SessionRecord).filter(
            SessionRecord.session_id == session_id
        ).first()

        adapter = self._build_adapter(session_id, record=record)

        # ── 读取 session 状态，触发自动压缩 ──────────────────────────────────
        state = self.store.get(session_id) or AgentState()
        context_tokens = record.context_tokens if record and record.context_tokens else 0

        model_setting = (
            self.db.query(ModelSetting).filter(
                ModelSetting.model_id == record.model_id,
                ModelSetting.provider_id == record.model_provider_id,
            ).first()
            if record and record.model_id and record.model_provider_id
            else None
        )
        # 无模型设置时退化为 context_tokens（比值=1.0），确保有历史 token 的会话仍能触发压缩
        context_length = model_setting.context_length if model_setting and model_setting.context_length else context_tokens
        session_type = record.session_type if record else "assistant"
        workspace_path = record.workspace_path if record else None
        if state.messages:
            auto_compact_result = CompactService(self.db).auto_compact_in_memory(
                state=state,
                context_tokens=context_tokens,
                context_length=context_length,
                keep_recent_count=2,
            )
            state = auto_compact_result.state

        # ── 加载 Agent 定义 + Skill ───────────────────────────────────────────
        if session_type == "coding":
            effective_agent_name = "software_engineer"
        else:
            effective_agent_name = agent_input.agent_name or "default"
        definition = AgentDefinitionService(self.db).load_definition(effective_agent_name)
        runtime_definition = SkillContextService(self.db).build_runtime_definition_with_skills(
            definition,
            agent_input,
            session_type=session_type,
            workspace_path=workspace_path,
        )

        # ── 读取审批策略 ──────────────────────────────────────────────────────
        profile_name = record.permission_profile if record and record.permission_profile else "conservative"
        approval_policy = PROFILES.get(profile_name, PROFILES["conservative"]).approval_policy

        return RunContext(
            state=state,
            definition=runtime_definition,
            adapter=adapter,
            approval_policy=approval_policy,
            effective_agent_name=effective_agent_name,
            workspace_path=record.workspace_path if record else None,
            session_type=session_type,
        )

    # ── 私有辅助 ──────────────────────────────────────────────────────────────

    def _build_adapter(self, session_id: str, record=None) -> ChatCompletionsAdapter:
        """构建 LLM Adapter 的实际逻辑，build() 和 build_adapter() 共用。"""
        from agent_prototype.infrastructure.llm.thinking_styles import build_thinking_payload

        if record is None:
            record = self.db.query(SessionRecord).filter(
                SessionRecord.session_id == session_id
            ).first()

        if record is None or record.model_provider_id is None or record.model_id is None:
            raise ValueError("当前会话未配置模型，请在设置中选择 Provider 和模型后再开始对话")

        provider = self.db.query(ProviderConfig).filter(
            ProviderConfig.id == record.model_provider_id
        ).first()
        if provider is None:
            raise ValueError("会话关联的 Provider 已被删除，请重新选择模型")

        model_setting = self.db.query(ModelSetting).filter(
            ModelSetting.model_id == record.model_id,
            ModelSetting.provider_id == record.model_provider_id,
        ).first()

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