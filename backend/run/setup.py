"""构建单次运行需要的稳定 setup。"""

from typing import Optional

from sqlalchemy.orm import Session

from backend.agent import AgentDefinition, load_agent_definition
from backend.context.compaction import HistoryCompactor
from backend.core.adapters.chat_completions import ChatCompletionsAdapter
from backend.prompt.builder import build_runtime_system_prompt
from backend.prompt.collect import collect_prompt_materials
from backend.run.types import RunInput, RunSetup
from backend.agent_loop.types import RunState
from backend.infra.db.orm_models import (
    ModelSetting,
    ProviderConfig,
    SessionRecord,
)
from backend.session.store import SessionStore
from backend.context.compaction import CompactService
from backend.prompt.strategies.thinking import build_thinking_payload
from backend.security.policy.types import PROFILES


def build_run_setup(db: Session, run_input: RunInput) -> RunSetup:
    """按主链顺序构建一次运行所需的稳定 setup。"""
    # 1. 读取 session 输入
    session_id = run_input.session_id
    session_record = load_session_record(
        db=db,
        session_id=session_id,
    )
    session_state = load_session_state(
        db=db,
        session_id=session_id,
    )

    # 2. 构建模型依赖
    model_adapter = build_model_adapter(
        db=db,
        session_id=session_id,
        record=session_record,
    )
    session_state = maybe_auto_compact_state(
        db=db,
        state=session_state,
        record=session_record,
        adapter=model_adapter,
    )

    # 3. 解析本轮 agent 与 prompt
    effective_agent_name = resolve_agent_name(
        run_input=run_input,
    )
    agent_definition = load_agent_definition(db, effective_agent_name)
    runtime_system_prompt = build_runtime_system_prompt_for_run(
        run_input=run_input,
        workspace_path=(session_record.workspace_path if session_record else None),
        definition=agent_definition,
    )

    # 4. 解析执行策略
    approval_policy = resolve_approval_policy(
        record=session_record,
    )

    # 5. 返回稳定 setup 对象
    return RunSetup(
        state=session_state,
        agent_profile=agent_definition,
        runtime_system_prompt=runtime_system_prompt,
        adapter=model_adapter,
        approval_policy=approval_policy,
        effective_agent_name=effective_agent_name,
        workspace_path=(session_record.workspace_path if session_record else ""),
    )


def build_runtime_system_prompt_for_run(
    *,
    run_input: RunInput,
    workspace_path: Optional[str],
    definition: AgentDefinition,
) -> str:
    """构建本轮真正传给模型的运行时系统提示词。"""
    # 1. 收集 prompt 物料
    materials = collect_prompt_materials(
        skill_name=run_input.skill_name,
        workspace_path=workspace_path,
    )

    # 2. 按固定顺序组装 prompt
    return build_runtime_system_prompt(
        available_skills=materials["available_skills"],
        selected_skill_content=materials["selected_skill_content"],
        local_rules_text=materials["local_rules_text"],
        user_profile_text=materials["user_profile_text"],
        agent_overlay_text=definition.system_prompt,
    )


def load_session_record(db: Session, session_id: str) -> Optional[SessionRecord]:
    """读取会话主记录。"""
    return (
        db.query(SessionRecord)
        .filter(SessionRecord.session_id == session_id)
        .first()
    )


def load_session_state(db: Session, session_id: str) -> RunState:
    """读取会话最新状态快照。"""
    return SessionStore(db).get(session_id=session_id) or RunState()


# === Resolution Helpers =====================================================

def resolve_context_length(
    db: Session,
    record: Optional[SessionRecord],
    fallback_tokens: int,
) -> int:
    """解析本次运行的上下文长度。"""
    model_setting = (
        db.query(ModelSetting)
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


def resolve_agent_name(run_input: RunInput) -> str:
    """解析本轮实际使用的 agent 名称。"""
    return run_input.agent_name or "default"


def resolve_approval_policy(record: Optional[SessionRecord]):
    """根据会话权限档位选择审批策略。"""
    profile_name = (
        record.permission_profile
        if record and record.permission_profile
        else "conservative"
    )
    return PROFILES.get(profile_name, PROFILES["conservative"]).approval_policy


# === Runtime Preparation ====================================================

def maybe_auto_compact_state(
    *,
    db: Session,
    state: RunState,
    record: Optional[SessionRecord],
    adapter: ChatCompletionsAdapter,
) -> RunState:
    """在进入 run 前按当前上下文预算执行一次自动压缩。"""
    if not state.messages:
        return state

    context_tokens = (
        record.context_tokens if record and record.context_tokens else 0
    )
    context_length = resolve_context_length(
        db=db,
        record=record,
        fallback_tokens=context_tokens,
    )
    compactor = HistoryCompactor(adapter)
    compact_result = CompactService(db).auto_compact_in_memory(
        state=state,
        context_tokens=context_tokens,
        context_length=context_length,
        compactor=compactor,
    )
    return compact_result.state


def build_model_adapter(
    db: Session,
    session_id: str,
    record: Optional[SessionRecord] = None,
) -> ChatCompletionsAdapter:
    """根据会话绑定的服务商和模型配置构建模型适配器。"""
    # 1. 读取 session 的模型绑定
    if record is None:
        record = load_session_record(
            db=db,
            session_id=session_id,
        )

    if (
        record is None
        or record.model_provider_id is None
        or record.model_id is None
    ):
        raise ValueError(
            "当前会话未配置模型，请在设置中选择 Provider 和模型后再开始对话"
        )

    # 2. 解析 provider 与 model 配置
    provider = (
        db.query(ProviderConfig)
        .filter(ProviderConfig.id == record.model_provider_id)
        .first()
    )
    if provider is None:
        raise ValueError("会话关联的 Provider 已被删除，请重新选择模型")

    model_setting = (
        db.query(ModelSetting)
        .filter(
            ModelSetting.model_id == record.model_id,
            ModelSetting.provider_id == record.model_provider_id,
        )
        .first()
    )

    # 3. 组装适配器参数
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
