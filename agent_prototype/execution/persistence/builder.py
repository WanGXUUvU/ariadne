"""
[九层模型 - L8 上下文装配与模型构建层 (Execution Layer)]

文件职责：
- 充当对话运行时上下文统一装配器（RunContextBuilder）。
- 读取数据库 Session 记录、拉取当前 Session 的最新状态快照并触发 L5 自动有损历史压缩评估。
- 调用 L6 层的统一装配器（ContextAssembler）拼装最终系统提示词、加载 Agent 预设人设。
- 读取审批档位策略（PROFILES），并动态实例化大模型底层适配器（ChatCompletionsAdapter）。

上游依赖：L8 执行层 (RunService)。
下游依赖：L6 统一装配器 (ContextAssembler)、L5 记忆层 (CompactService & store.py)、L1 模型层 (ChatCompletionsAdapter)、L7 安全策略层 (PROFILES)。
"""
from typing import Optional
from sqlalchemy.orm import Session

from agent_prototype.security.policy import PROFILES
from agent_prototype.infra.db.orm_models import ModelSetting, ProviderConfig, SessionRecord
from agent_prototype.memory.session.store import SqliteSessionStore
from agent_prototype.core.adapters.chat_completions import ChatCompletionsAdapter
from agent_prototype.core.types import AgentInput, AgentState
from agent_prototype.security.policy import ApprovalPolicy
from agent_prototype.core.types import AgentDefinition
from agent_prototype.agent.definition import AgentDefinitionService
from agent_prototype.memory.summary.service import CompactService
from agent_prototype.context.assembler import ContextAssembler
from agent_prototype.execution.persistence.types import RunContext


class RunContextBuilder:
    """这是一个"运行物料装配工"。
    它的核心工作是在智能体开始跑起来之前，把所有的背景物料（比如聊天状态、系统提示词、大模型连接器、审批策略等）给搜集打包好，
    装进 `RunContext` 这个小背包里，然后递给执行服务 `RunService`。
    """

    def __init__(self, db: Session):
        """初始化这个装配工，给他连上数据库，并且给他分配一个会话存储仓库，方便他查数据和状态。

        需要拿到的东西：
        - db: 数据库连接会话对象。
        """
        self.db = db
        self.store = SqliteSessionStore(db)

    def build_adapter(self, session_id: str) -> ChatCompletionsAdapter:
        """快捷通道：不组装完整的物料背包，只单独把大模型适配器（也就是跟大模型沟通的电话线）给接通。
        适合在"恢复运行"（resume）等不需要其他复杂背景物料的场景下使用。

        需要拿到的东西：
        - session_id: 会话的唯一身份证号（ID）。

        会给出来的结果：
        - 一个接通了大模型的 ChatCompletionsAdapter 适配器对象。
        """
        return self._build_adapter(session_id)

    def build(self, agent_input: AgentInput) -> RunContext:
        """火力全开！把这次运行需要的所有上下文背景物料给完整拼装出来。
        它会去读数据库里的会话记录，接通大模型适配器，拿出来历史聊天记录并看看要不要压缩精简，
        再去加载智能体的人设定义，把本地工作区的文件缝合进系统提示词，最后配上安全审批策略，打包塞进小背包里。

        需要拿到的东西：
        - agent_input: 用户发起的输入请求参数，里面有会话 ID 和智能体名字等。

        会给出来的结果：
        - 一个装满了所有必要运行时物料的 RunContext 小背包对象。
        """
        session_id = agent_input.session_id

        # ──【第一层：元数据加载层 L0/L8】读取数据库会话元数据 ───────────────────────
        # 从 SQLite 中读取会话的主表记录，以获取其绑定的模型、厂商、工作区路径及权限配置文件。
        record = self.db.query(SessionRecord).filter(
            SessionRecord.session_id == session_id
        ).first()

        # ──【第二层：大模型通道层 L1】构建 LLM 客户端适配器 ─────────────────────────
        # 依靠数据库里的 Provider 及 Model 配置，拉起具备思考流与参数生成功能的适配器实例。
        adapter = self._build_adapter(session_id, record=record)

        # ──【第三层：历史与摘要容量层 L5/L6】加载历史消息并触发自动压缩评估 ────────────
        # 1. 从 DB 中读出本会话当前的完整对话历史。
        state = self.store.get(session_id) or AgentState()
        context_tokens = record.context_tokens if record and record.context_tokens else 0

        # 2. 查询底层大模型的最大 Token 上下文限制，用以计算占比比率。
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
        
        # 3. 如果有历史消息，自动评估并执行"前情提要式"的内存压缩，腾出上下文额度。
        if state.messages:
            auto_compact_result = CompactService(self.db).auto_compact_in_memory(
                state=state,
                context_tokens=context_tokens,
                context_length=context_length,
                keep_recent_count=2,
            )
            state = auto_compact_result.state

        # ──【第四层：智能体模板层 L8】决定并加载智能体基础定义配置 ──────────────────
        # 根据会话类型进行智能映射：若为 Coding 编码会话则强制使用软件工程师角色；
        # 若为 Assistant 聊天会话，则回退至用户自定义配置或默认智能体。
        if session_type == "coding":
            effective_agent_name = "software_engineer"
        else:
            effective_agent_name = agent_input.agent_name or "default"
        definition = AgentDefinitionService(self.db).load_definition(effective_agent_name)

        # ──【第五层：上下文装配层 L6】缝合本地物理规约、灵魂人设与技能清单 ────────────
        # 1. 统一委托 ContextAssembler，去工作区文件夹下异步读取 AGENTS.md, SOUL.md, USER.md。
        assembler = ContextAssembler(self.db)
        assembled_ctx = assembler.assemble(
            agent_input=agent_input,
            session_type=session_type,
            workspace_path=workspace_path,
            definition=definition,
        )

        # 2. 将装配、缝合完毕的全新 system_prompt 覆盖写入本次运行的副本中。
        runtime_definition = definition.model_copy(
            update={"system_prompt": assembled_ctx.system_prompt}
        )

        # ──【第六层：安全网关策略层 L8】加载人工审批与信任决策门禁 ──────────────────
        # 读取会话当前的权限配置文件（conservative/standard/full-auto），并映射为运行时拦截策略。
        profile_name = record.permission_profile if record and record.permission_profile else "conservative"
        approval_policy = PROFILES.get(profile_name, PROFILES["conservative"]).approval_policy

        # ──【第七层：输出构建】组装完整的运行时上下文背包 ──────────────────────────
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
        """内部核心私有方法：真正去读数据库里的模型配置，把大模型适配器给生产出来的实际逻辑。
        它还会把模型的"思考深度"配置（thinking payload）给合理加进去。

        需要拿到的东西：
        - session_id: 会话的唯一身份证号。
        - record: 已经读出来的数据库会话记录对象（如果传了就省得再去查一次了）。

        会给出来的结果：
        - 一个配置完美、直接可以发请求的 ChatCompletionsAdapter 适配器对象。
        """
        from agent_prototype.prompt.strategies.thinking import build_thinking_payload

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