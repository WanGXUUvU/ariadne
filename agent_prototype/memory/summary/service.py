"""
[九层模型 - L5 记忆层 (Memory Layer)]

文件职责：
- 管理有损对话历史压缩生命周期（CompactService）。
- 负责快照状态（Snapshot）持久化更新、数据库事务管理、以及 Session 主Runs状态（活跃/非活跃）维护。
- 拒绝任何 LLM 直接调用与 L8 执行层依赖，转而通过依赖注入的 L6 HistoryCompactor 执行大模型压缩。

上游依赖：L8 执行层 (RunContextBuilder)、L10 接口层 (GET/POST 路由)。
下游依赖：L6 上下文压缩层 (HistoryCompactor / compaction.py)、L5 仓储层 (SqliteSessionStore)、L0 基础设施 (db)。
"""
import os
from typing import Optional
from sqlalchemy.orm import Session

from agent_prototype.infra.db.orm_models import SessionRecord, ModelSetting, ProviderConfig
from agent_prototype.api.dto.schemas import AgentState, CompactInput, CompactOutput, ChatMessage
from agent_prototype.memory.session.store import SqliteSessionStore
from agent_prototype.context.compaction import (
    build_compact_prompt,
    compact_state_with_summary,
    split_messages_for_compaction,
    HistoryCompactor
)
from agent_prototype.model.adapters.chat_completions import ChatCompletionsAdapter

COMPACT_MODEL = os.getenv("COMPACT_MODEL", "deepseek-v4-flash")


class CompactService:
    """上下文长历史压缩管理服务类 (OOP)
    
    这个类是“聊天历史瘦身教练”。它的主要任务是防止聊天记录太长，导致 AI 记不住或者消耗太多 Token（算力话费）。当聊天历史太长时，它会把旧的聊天内容打包总结成一段简短的“前情提要”，只留下最近的几条聊天消息，从而给聊天上下文“减肥瘦身”。
    """
    
    def __init__(self, db: Session):
        """初始化瘦身教练，带上数据库的钥匙并叫上底下的“数据仓库”。

        需要拿到的东西：
        - db (Session): 操作数据库的钥匙。
        """
        self.db = db
        self.store = SqliteSessionStore(db)

    def _build_session_adapter(self, session_id: str) -> ChatCompletionsAdapter:
        """根据会话 ID 去数据库里查找这个会话关联的 AI 模型和 API Key，并创建对应的 AI 客户端适配器，好让它一会儿能找 AI 进行历史压缩总结。

        需要拿到的东西：
        - session_id (str): 会话 ID。

        会给出来的结果：
        - ChatCompletionsAdapter: 已经配置妥当、随时能向大模型发请求的 AI 客户端适配器。
        """
        from agent_prototype.prompt.strategies.thinking import build_thinking_payload

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

    def auto_compact_in_memory(
        self,
        state: AgentState,
        context_tokens: int,
        context_length: int,
        keep_recent_count: int,
        force: bool = False,
        compactor: Optional[HistoryCompactor] = None,
    ) -> CompactOutput:
        """在内存里模拟做一次瘦身，不做持久化落库。
        它会先看看目前的 Token 消耗是不是已经到了临界线（通常占用了模型总容量的 70% 以上）。如果是，或者被强制要求压缩，它就会把除了最近留底（keep_recent_count 条）以外的历史消息，交给大模型做个提炼总结，然后把总结出的“前情提要”放到第一条，把其余旧消息删掉，从而给聊天历史减负。

        需要拿到的东西：
        - state (AgentState): 当前的聊天状态（也就是包含哪些消息）。
        - context_tokens (int): 目前聊天内容大约消耗了多少 Token。
        - context_length (int): 这个模型最大支持多少 Token 上下文。
        - keep_recent_count (int): 瘦身时，最少需要在底部原封不动保留几条最新的消息。
        - force (bool, 默认 False): 是否强制进行压缩（即使还没达到 70% 阈值）。
        - compactor (HistoryCompactor, 可选): 执行压缩总结的压缩器实例。

        会给出来的结果：
        - CompactOutput: 瘦身结果数据包。包含did_compact（有没有做瘦身）、瘦身后的 state（如果做了，就包含前情提要+最近消息；没做就是原样），以及被删掉的消息数量。
        """
        if not force:
            if context_tokens == 0 or context_length == 0:
                return CompactOutput(state=state, did_compact=False, removed_count=0)
            if context_tokens / context_length < 0.7:
                return CompactOutput(state=state, did_compact=False, removed_count=0)
                
        _, middle_messages, _ = split_messages_for_compaction(
            state.messages,
            keep_recent_count=keep_recent_count,
        )

        if not middle_messages:
            return CompactOutput(state=state, did_compact=False, removed_count=0)

        # 核心重构：使用外部传入的 compactor 或是构建默认环境变量 compactor
        if compactor is None:
            adapter = ChatCompletionsAdapter(model=COMPACT_MODEL)
            compactor = HistoryCompactor(adapter)

        summary_text = compactor.compact(state.messages, keep_recent=keep_recent_count)

        if not summary_text:
            raise ValueError("Compact summary is empty")

        compact_tokens: Optional[int] = compactor.last_compact_tokens

        compact_result = compact_state_with_summary(
            state=state,
            summary_text=summary_text,
            keep_recent_count=keep_recent_count,
        )
        if compact_tokens is not None:
            compact_result = compact_result.model_copy(update={"compact_tokens": compact_tokens})
            
        return compact_result

    def compact_session(self, payload: CompactInput) -> CompactOutput:
        """正式执行聊天历史有损压缩（瘦身）的入口。
        它会去数据库读出指定会话的全部聊天历史，判断是否达到了触发压缩的条件（或者用户强制触发）。一旦决定压缩，它就调用内存压缩算法搞定总结，然后把压缩后带有“前情提要”的最新历史快照存回数据库。同时它还会贴心地把很多历史运行记录标记为非活跃，防止前端界面加载时过于臃肿。

        需要拿到的东西：
        - payload (CompactInput): 压缩请求入参，主要有会话 ID（session_id）、触发消息数阈值（trigger_threshold）、底保留消息数（keep_recent_count）和是否强压（force）。

        会给出来的结果：
        - CompactOutput: 包含有没有真正做压缩、压缩后聊天状态等信息的瘦身数据包。
        """
        state = self.store.get(payload.session_id)
        if state is None:
            raise ValueError("Session not found")

        record = self.db.query(SessionRecord).filter(SessionRecord.session_id == payload.session_id).first()
        context_tokens = record.context_tokens or 0 if record else 0

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
        context_length = model_setting.context_length or 0 if model_setting else 0

        # 无 token 信息时退回消息数量阈值判断
        force_by_count = (
            (context_tokens == 0 or context_length == 0)
            and len(state.messages) >= payload.trigger_threshold
        )

        # 获取当前会话的模型适配器并构造 L6 压缩器
        adapter = self._build_session_adapter(payload.session_id)
        compactor = HistoryCompactor(adapter)

        # 调用自身的内存压缩逻辑
        compact_result = self.auto_compact_in_memory(
            state=state,
            context_tokens=context_tokens,
            context_length=context_length,
            keep_recent_count=payload.keep_recent_count,
            force=payload.force or force_by_count,
            compactor=compactor,
        )

        if not compact_result.did_compact:
            return compact_result

        record = self.store.read_session_record(payload.session_id)
        try:
            if compact_result.compact_tokens is not None:
                new_context_tokens = compact_result.compact_tokens
            else:
                new_context_tokens = sum(len(m.content or "") for m in compact_result.state.messages) // 4
                
            self.store.upsert_session_snapshot(
                payload.session_id,
                state=compact_result.state,
                session_name=record.session_name if record else payload.session_id,
                last_agent_name=record.last_agent_name if record else None,
                last_skill_name=record.last_skill_name if record else None,
                last_reply_preview=record.last_reply_preview if record else None,
                context_tokens=new_context_tokens,
            )
            recent_active_count = payload.keep_recent_count // 2
            runs = self.store.list_run_records(payload.session_id)
            # 过滤出主对话 Runs (Scenario C 过滤)
            parent_runs = [r for r in runs if r.parent_run_id is None]
            runs_count = len(parent_runs)
            for idx, run in enumerate(parent_runs):
                if idx == 0:
                    continue
                if idx >= (runs_count - recent_active_count):
                    continue
                # 设定为非活跃 (is_active = "0")
                run.is_active = "0"

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return compact_result
