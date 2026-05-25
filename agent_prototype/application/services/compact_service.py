import os
from typing import Optional
from sqlalchemy.orm import Session

from agent_prototype.infrastructure.database.models import SessionRecord, ModelSetting
from agent_prototype.interface.dto.schemas import AgentState, CompactInput, CompactOutput, ChatMessage
from agent_prototype.infrastructure.database.repositories.session_store import SqliteSessionStore
from agent_prototype.application.runtime.context.compaction import (
    build_compact_prompt,
    compact_state_with_summary,
    split_messages_for_compaction
)
from agent_prototype.infrastructure.llm.chat_completions_adapter import ChatCompletionsAdapter
from agent_prototype.infrastructure.llm.model_types import ModelConfig, ModelRequest

COMPACT_MODEL = os.getenv("COMPACT_MODEL", "deepseek-v4-flash")


class CompactService:
    """上下文长历史压缩管理服务类 (OOP)
    
    职责：
    1. 评估会话历史占用的 Token 比率是否超过阈值并执行有损压缩；
    2. 提供无状态的纯内存计算，以及有状态的 Snapshot 持久化落库。
    """
    
    def __init__(self, db: Session):
        """注入 db 会话并聚合 SqliteSessionStore 仓储"""
        self.db = db
        self.store = SqliteSessionStore(db)

    def _get_session_adapter(self, session_id: str) -> ChatCompletionsAdapter:
        """延迟导入 RunContextBuilder 以避免循环依赖，构建该 session 的 LLM Adapter。"""
        from agent_prototype.application.services.run.run_context_builder import RunContextBuilder
        return RunContextBuilder(self.db).build_adapter(session_id)

    def auto_compact_in_memory(
        self,
        state: AgentState,
        context_tokens: int,
        context_length: int,
        keep_recent_count: int,
        force: bool = False,
        adapter: Optional[ChatCompletionsAdapter] = None,
    ) -> CompactOutput:
        """评估并计算无状态压缩结果（纯内存评估，不涉及物理落库或事务控制）"""
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

        compact_prompt = build_compact_prompt(middle_messages)

        # 使用外部传入的适配器，或退回默认环境变量适配器
        adapter = adapter or ChatCompletionsAdapter(model=COMPACT_MODEL)
        request = ModelRequest(
            messages=[
                ChatMessage(role="system", content=compact_prompt),
            ],
            tools=[],
            config=ModelConfig(stream=False),
            metadata={"mode": "compact"},
        )
        summary_response = adapter.generate(request)
        summary_text = (summary_response.content or "").strip()

        if not summary_text:
            raise ValueError("Compact summary is empty")

        compact_tokens: Optional[int] = None
        if summary_response.usage and summary_response.usage.input_tokens:
            compact_tokens = summary_response.usage.input_tokens

        compact_result = compact_state_with_summary(
            state=state,
            summary_text=summary_text,
            keep_recent_count=keep_recent_count,
        )
        if compact_tokens is not None:
            compact_result = compact_result.model_copy(update={"compact_tokens": compact_tokens})
            
        return compact_result

    def compact_session(self, payload: CompactInput) -> CompactOutput:
        """有状态压缩入口：读取数据库 Session 快照，执行压缩，更新 Snapshot 并持久化"""
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

        # 调用自身的内存压缩逻辑（传入 session 对应的适配器）
        compact_result = self.auto_compact_in_memory(
            state=state,
            context_tokens=context_tokens,
            context_length=context_length,
            keep_recent_count=payload.keep_recent_count,
            force=payload.force or force_by_count,
            adapter=self._get_session_adapter(payload.session_id),
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

