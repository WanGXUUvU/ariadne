"""Session 存储访问层。

职责：
- 维护 session 快照和主记录。
- 提供 session 列表、详情、重命名和删除能力。

上游：
- RunService
- CompactService
- API routes

下游：
- SessionRecord / SessionRunRecord 等 ORM 模型

不负责：
- 不管理 run trace 事件内容。
- 不负责业务层校验和 HTTP 语义。
"""

import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session
from agent_prototype.execution.runtime.types import AgentState
from agent_prototype.infra.db.orm_models import (
    SessionRecord,
    SessionRunRecord,
    SessionRunEventRecord,
    ToolCallRecord,
)

_UNSET = object()


class SessionStore:
    """围绕 session 相关数据的 SQLite store。"""

    def __init__(self, db: Session):
        self.db = db

    # ── Session 快照操作 ───────────────────────────────────────────────────

    def get(self, session_id: str) -> Optional[AgentState]:
        """获取一个会话当前的聊天状态。"""
        return self.read_session_state(session_id)

    def save_state(
        self,
        session_id: str,
        state: AgentState,
        session_name: Optional[str] = None,
        last_agent_name=_UNSET,
        last_reply_preview=_UNSET,
        context_tokens: Optional[int] = None,
        workspace_path=_UNSET,
        workspace_name=_UNSET,
        session_type=_UNSET,
    ) -> SessionRecord:
        """保存或更新一个 session 的状态快照。"""
        state_json = json.dumps(state.model_dump(), ensure_ascii=False)
        message_count = len(state.messages)
        record = self.db.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()

        if record:
            record.state_json = state_json
            if session_name is not None:
                record.session_name = session_name
            elif not record.session_name:
                record.session_name = session_id

            if last_agent_name is not _UNSET:
                record.last_agent_name = last_agent_name
            if last_reply_preview is not _UNSET:
                record.last_reply_preview = last_reply_preview

            record.message_count = message_count

            if workspace_name is not _UNSET:
                record.workspace_name = workspace_name
            if workspace_path is not _UNSET:
                record.workspace_path = workspace_path
            if session_type is not _UNSET:
                record.session_type = session_type
            record.context_tokens = context_tokens
        else:
            record = SessionRecord(
                session_id=session_id,
                session_name=session_name or session_id,
                state_json=state_json,
                last_agent_name=None if last_agent_name is _UNSET else last_agent_name,
                message_count=message_count,
                last_reply_preview=None if last_reply_preview is _UNSET else last_reply_preview,
                context_tokens=context_tokens,
                workspace_path=None if workspace_path is _UNSET else workspace_path,
                workspace_name=None if workspace_name is _UNSET else workspace_name,
                session_type="coding" if session_type is _UNSET else session_type,
            )
            self.db.add(record)

        return record

    # ── Session CRUD ───────────────────────────────────────────────────────

    def rename_session(self, session_id, new_name: str) -> bool:
        """重命名指定 session。"""
        record = self.db.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()
        if not record:
            return False
        record.session_name = new_name
        return True

    def delete_session(self, session_id: str) -> bool:
        """删除指定 session 及其关联 run 数据。"""
        record = self.db.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()
        if not record:
            return False
        run_id_query = select(SessionRunRecord.run_id).where(
            SessionRunRecord.session_id == session_id
        )
        self.db.query(ToolCallRecord).filter(ToolCallRecord.run_id.in_(run_id_query)).delete(
            synchronize_session=False
        )
        self.db.query(SessionRunEventRecord).filter(
            SessionRunEventRecord.run_id.in_(run_id_query)
        ).delete(synchronize_session=False)
        self.db.query(SessionRunRecord).filter(SessionRunRecord.session_id == session_id).delete(
            synchronize_session=False
        )
        self.db.delete(record)
        return True

    def list_sessions(self) -> list[SessionRecord]:
        """返回所有 session，按更新时间倒序排列。"""
        return (
            self.db.query(SessionRecord)
            .order_by(SessionRecord.updated_at.desc(), SessionRecord.session_id.asc())
            .all()
        )

    def load_record(self, session_id: str) -> Optional[SessionRecord]:
        """读取 session 主记录。"""
        return self.db.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()

    def read_session_state(self, session_id: str) -> Optional[AgentState]:
        """读取并反序列化 session 状态快照。"""
        record = self.load_record(session_id)
        if not record:
            return None
        return AgentState.model_validate(json.loads(record.state_json))

    # ── Run 重置 ───────────────────────────────────────────────────────────

    def reset_session_runs(self, session_id: str) -> None:
        """将某个 session 下的顶层 run 标记为非活跃。"""
        self.db.query(SessionRunRecord).filter(
            SessionRunRecord.session_id == session_id, SessionRunRecord.parent_run_id.is_(None)
        ).update({"is_active": "0"}, synchronize_session=False)
