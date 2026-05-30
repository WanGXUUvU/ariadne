"""工具调用生命周期观察者。

职责：
- 封装工具执行过程中所有与数据库相关的副作用回调。
- 把 on_tool_start / on_tool_finish / on_approval_required 从 run_service 中解耦出来。
上游：run_service.py 构造并注入
下游：SqliteRunStore / SqliteApprovalStore（通过构造参数传入）
"""

from sqlalchemy.orm import Session
from typing import Optional

from agent_prototype.security.approval.store import SqliteApprovalStore
from agent_prototype.memory.run.store import SqliteRunStore
from agent_prototype.execution.persistence.types import AgentInput
from agent_prototype.execution.runtime.types import AgentEvent, AgentState


class ToolRunObserver:
    """工具调用生命周期观察者，专门负责落库副作用。"""

    def __init__(
        self,
        db: Session,
        run_store: SqliteRunStore,
        approval_store: SqliteApprovalStore,
        session_id: str,
        run_id: str,
        agent_input: AgentInput,
    ):
        self.db = db
        self.run_store = run_store
        self.approval_store = approval_store
        self.session_id = session_id
        self.run_id = run_id
        self.agent_input = agent_input

    # ── 三个回调，直接挂给 async_stream_run ──────────────────────────────────

    def on_tool_start(self, tool_name: str, tool_call_id: str, input_json: str) -> int:
        """工具开始执行时，创建 tool_call 中间态记录。"""
        record_id = self.run_store.create_tool_call(
            run_id=self.run_id,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            input_json=input_json,
        )
        self.db.commit()
        return record_id

    def on_tool_finish(self, record_id: int, status: str, result_json: Optional[str]) -> None:
        """工具执行完毕时，更新 tool_call 记录状态。"""
        self.run_store.finish_tool_call(
            record_id=record_id,
            status=status,
            result_json=result_json,
        )
        self.db.commit()

    def on_approval_required(
        self,
        tool_call_id: str,
        tool_name: str,
        arguments: str,
        saved_messages: Optional[list],
        event_index: int,
        batch_id: Optional[str] = None,
    ) -> str:
        """需要人工审批时，写入 approval 记录并返回记录 ID。"""
        record = self.approval_store.create(
            session_id=self.session_id,
            run_id=self.run_id,
            batch_id=batch_id or self.run_id,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            arguments=arguments,
            saved_messages=saved_messages,
            event_index=event_index,
        )
        self.db.commit()
        return record.id

    # ── 暂停处理 ─────────────────────────────────────────────────────────────

    def handle_paused(
        self,
        state: AgentState,
        events: list[AgentEvent],
        partial_reply: str,
    ) -> None:
        """审批暂停时，存储当前 run 的中间状态,并刷新状态快照"""
        pending = self.approval_store.get_next_pending_for_run(self.run_id)
        if pending is not None:
            self.approval_store.refresh_pending_saved_messages_for_batch(
                batch_id=pending.batch_id or pending.run_id,
                saved_messages=state.messages,
            )
        self.run_store.save_partial_run(
            session_id=self.session_id,
            run_id=self.run_id,
            agent_name=self.agent_input.agent_name,
            skill_name=self.agent_input.skill_name,
            user_input=self.agent_input.user_input,
            partial_reply=partial_reply,
            state=state,
            events=events,
        )
        self.run_store.update_run_status(run_id=self.run_id, status="paused")
        self.db.commit()
