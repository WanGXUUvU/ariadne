"""工具调用生命周期观察者。

职责：
- 封装工具执行过程中所有与数据库相关的副作用回调。
- 把 on_tool_start / on_tool_finish / on_approval_required 从 run_service 中解耦出来。
上游：run_service.py 构造并注入
下游：RunTraceStore / SqliteApprovalStore（通过构造参数传入）
"""

from sqlalchemy.orm import Session
from typing import Optional

from agent_prototype.security.approval.store import SqliteApprovalStore
from agent_prototype.memory.run.store import RunTraceStore
from agent_prototype.execution.persistence.types import AgentInput


class ToolTracer:
    """工具调用生命周期观察者，专门负责落库副作用。"""

    def __init__(
        self,
        db: Session,
        run_store: RunTraceStore,
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
