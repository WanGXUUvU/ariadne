"""对话历史压缩服务。

职责：
- 评估是否需要压缩历史消息。
- 驱动 HistoryCompactor 生成摘要。
- 将压缩后的状态快照写回 session，并收缩历史 run 的活跃范围。

上游：
- RunContextFactory
- compact API route

下游：
- SessionStore / RunTraceStore
- HistoryCompactor / compaction helpers

不负责：
- 不直接调用模型；模型能力通过注入的 HistoryCompactor 提供。
- 不感知 HTTP 语义。
"""

from typing import Optional
from sqlalchemy.orm import Session

from agent_prototype.infra.db.orm_models import SessionRecord, ModelSetting
from agent_prototype.memory.summary.types import CompactInput, CompactOutput
from agent_prototype.memory.session.store import SessionStore
from agent_prototype.memory.run.store import RunTraceStore
from agent_prototype.context.compaction import (
    compact_state_with_summary,
    split_messages_for_compaction,
    HistoryCompactor,
)
from agent_prototype.execution.runtime.types import AgentState


class CompactService:
    """管理对话历史压缩生命周期。"""

    def __init__(self, db: Session):
        """使用当前 DB session 装配压缩服务。"""
        self.db = db
        self.store = SessionStore(db)
        self._run_store = RunTraceStore(db)

    def auto_compact_in_memory(
        self,
        state: AgentState,
        context_tokens: int,
        context_length: int,
        keep_recent_count: int,
        compactor: HistoryCompactor,
        force: bool = False,
    ) -> CompactOutput:
        """在内存中评估并执行一次压缩，不做持久化。"""
        if not force:
            if context_tokens == 0 or context_length == 0:
                return CompactOutput(state=state, did_compact=False, removed_count=0)
            if context_tokens / context_length < 0.7:
                return CompactOutput(state=state, did_compact=False, removed_count=0)

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
        """对指定 session 执行压缩，并将结果持久化。"""
        state = self.store.get(payload.session_id)
        if state is None:
            raise ValueError("Session not found")

        record = (
            self.db.query(SessionRecord)
            .filter(SessionRecord.session_id == payload.session_id)
            .first()
        )
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
        force_by_count = (context_tokens == 0 or context_length == 0) and len(
            state.messages
        ) >= payload.trigger_threshold

        from agent_prototype.execution.run_context_factory import RunContextFactory

        adapter = RunContextFactory(self.db).create_adapter(payload.session_id)
        compactor = HistoryCompactor(adapter)

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

        record = self.store.load_record(payload.session_id)
        try:
            if compact_result.compact_tokens is not None:
                new_context_tokens = compact_result.compact_tokens
            else:
                new_context_tokens = (
                    sum(len(m.content or "") for m in compact_result.state.messages) // 4
                )

            self.store.save_state(
                payload.session_id,
                state=compact_result.state,
                session_name=record.session_name if record else payload.session_id,
                last_agent_name=record.last_agent_name if record else None,
                last_reply_preview=record.last_reply_preview if record else None,
                context_tokens=new_context_tokens,
            )
            recent_active_count = payload.keep_recent_count // 2
            runs = self._run_store.list_run_records(payload.session_id)
            parent_runs = [r for r in runs if r.parent_run_id is None]
            runs_count = len(parent_runs)
            for idx, run in enumerate(parent_runs):
                if idx == 0:
                    continue
                if idx >= (runs_count - recent_active_count):
                    continue
                run.is_active = "0"

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        return compact_result
