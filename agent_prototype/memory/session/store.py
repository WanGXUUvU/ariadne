"""Session 存储访问层。

职责：
- session 快照的读取与更新
- session 列表、详情查询
- session 的重命名与删除

Run/Trace 相关操作请直接使用 run_store.py（SqliteRunStore）。
"""

import json
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session
from agent_prototype.core.types import AgentEvent, AgentState
from agent_prototype.infra.db.orm_models import SessionRecord, SessionRunRecord, SessionRunEventRecord, ToolCallRecord

_UNSET = object()


class SqliteSessionStore:
    """围绕 session 相关数据的 SQLite store。
    
    这个类是"会话数据仓库"。它就像是直接在数据库里干脏活累活的底层工人，专门负责会话数据的读取和写入。
    """

    def __init__(self, db: Session):
        self.db = db

    # ── Session 快照操作 ───────────────────────────────────────────────────

    def get(self, session_id: str) -> Optional[AgentState]:
        """获取一个会话当前的聊天状态。"""
        return self.read_session_state(session_id)

    def upsert_session_snapshot(
        self,
        session_id: str,
        state: AgentState,
        session_name: Optional[str] = None,
        last_agent_name=_UNSET,
        last_skill_name=_UNSET,
        last_reply_preview=_UNSET,
        context_tokens: Optional[int] = None,
        workspace_path=_UNSET,
        workspace_name=_UNSET,
        session_type=_UNSET,
    ) -> SessionRecord:
        """保存或更新会话的"快照"。"""
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

            if last_skill_name is not _UNSET:
                record.last_skill_name = last_skill_name
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
                last_skill_name=None if last_skill_name is _UNSET else last_skill_name,
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
        """在数据库里给指定会话改名。"""
        record = self.db.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()
        if not record:
            return False
        record.session_name = new_name
        return True

    def delete_session(self, session_id: str) -> bool:
        """在数据库里彻底把一个会话连根拔除。"""
        record = self.db.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()
        if not record:
            return False
        run_id_subq = (
            self.db.query(SessionRunRecord.run_id)
            .filter(SessionRunRecord.session_id == session_id)
            .subquery()
        )
        self.db.query(ToolCallRecord).filter(ToolCallRecord.run_id.in_(run_id_subq)).delete(synchronize_session=False)
        self.db.query(SessionRunEventRecord).filter(SessionRunEventRecord.run_id.in_(run_id_subq)).delete(synchronize_session=False)
        self.db.query(SessionRunRecord).filter(SessionRunRecord.session_id == session_id).delete(synchronize_session=False)
        self.db.delete(record)
        return True

    def list_sessions(self) -> list[SessionRecord]:
        """获取数据库中所有的会话列表。"""
        return (
            self.db.query(SessionRecord)
            .order_by(SessionRecord.updated_at.desc(), SessionRecord.session_id.asc())
            .all()
        )

    def read_session_record(self, session_id: str) -> Optional[SessionRecord]:
        """根据会话 ID 查出它在数据库里的主记录对象。"""
        return (
            self.db.query(SessionRecord)
            .filter(SessionRecord.session_id == session_id)
            .first()
        )

    def read_session_state(self, session_id: str) -> Optional[AgentState]:
        """读取并反序列化一个会话的完整聊天状态。"""
        record = self.read_session_record(session_id)
        if not record:
            return None
        return AgentState.model_validate(json.loads(record.state_json))

    # ── Run 重置 ───────────────────────────────────────────────────────────

    def reset_session_runs(self, session_id: str) -> None:
        """把某个会话下的所有核心运行记录标记为"非活跃"。"""
        self.db.query(SessionRunRecord).filter(
            SessionRunRecord.session_id == session_id,
            SessionRunRecord.parent_run_id == None
        ).update({"is_active": "0"}, synchronize_session=False)
