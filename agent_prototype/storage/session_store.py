"""Session / Trace 存储访问层。

这个文件封装 SQLite 上的常用读写动作：
- session 快照的读取与更新
- run trace 的写入
- session 列表、详情、trace 的查询

上层代码尽量通过这些方法拿数据，而不是在 route / service 里直接写 ORM 查询。
"""

import json
from typing import Optional

from sqlalchemy.orm import Session

from ..core.schemas import AgentEvent, AgentState
from .models import SessionRecord, SessionRunEventRecord, SessionRunRecord


class SqliteSessionStore:
    """围绕 session 相关数据的 SQLite store。"""

    def __init__(self, db: Session):
        """输入：数据库会话。输出：初始化后的 SqliteSessionStore 实例。"""
        self.db = db

    def get(self, session_id: str) -> Optional[AgentState]:
        """输入：session_id。输出：该 session 的 AgentState，找不到时返回 None。"""

        return self.read_session_state(session_id)

    def upsert_session_snapshot(
        self,
        session_id: str,
        state: AgentState,
        session_name: Optional[str] = None,
        last_agent_name: Optional[str] = None,
        last_skill_name: Optional[str] = None,
        last_reply_preview: Optional[str] = None,
    ) -> SessionRecord:
        """输入：session 标识、状态快照和若干元数据。输出：插入或更新后的 SessionRecord。

        `upsert` 的意思是：
        - 有旧记录就更新
        - 没有旧记录就创建
        """

        # 数据库不能直接存 Pydantic 对象，所以先转字典，再序列化成 JSON 字符串。
        state_json = json.dumps(state.model_dump(), ensure_ascii=False)
        message_count = len(state.messages)
        record = self.db.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()

        if record:
            record.state_json = state_json
            if session_name is not None:
                record.session_name = session_name
            elif not record.session_name:
                record.session_name = session_id
            record.last_agent_name = last_agent_name
            record.last_reply_preview = last_reply_preview
            record.message_count = message_count
            record.last_skill_name = last_skill_name
        else:
            record = SessionRecord(
                session_id=session_id,
                session_name=session_name or session_id,
                state_json=state_json,
                last_agent_name=last_agent_name,
                last_skill_name=last_skill_name,
                message_count=message_count,
                last_reply_preview=last_reply_preview,
            )
            self.db.add(record)

        return record

    def save_run_trace(
        self,
        *,
        session_id: str,
        run_id: str,
        agent_name: Optional[str],
        skill_name: Optional[str],
        user_input: str,
        reply: str,
        events: list[AgentEvent],
    ) -> SessionRunRecord:
        """输入：一次 run 的摘要字段和事件列表。输出：新建的 SessionRunRecord。"""

        run_record = SessionRunRecord(
            session_id=session_id,
            run_id=run_id,
            agent_name=agent_name,
            skill_name=skill_name,
            user_input=user_input,
            reply=reply,
            event_count=len(events),
        )
        self.db.add(run_record)

        # `enumerate(events)` 会同时拿到“下标 + 元素本身”，适合落 event 顺序。
        for index, event in enumerate(events):
            event_dict = event.model_dump(exclude_none=True)
            self.db.add(
                SessionRunEventRecord(
                    run_id=run_id,
                    event_index=index,
                    type=event_dict["type"],
                    content=event_dict.get("content") or "",
                    tool_name=event_dict.get("tool_name"),
                    tool_call_id=event_dict.get("tool_call_id"),
                    tool_result_json=(
                        json.dumps(event_dict.get("tool_result"), ensure_ascii=False)
                        if event_dict.get("tool_result")
                        else None
                    ),
                )
            )

        return run_record

    def delete(self, session_id: str) -> None:
        """输入：session_id。输出：无，副作用是删除这个 session 的主记录。"""

        record = self.db.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()
        if record:
            self.db.delete(record)
            self.db.commit()

    def list_run_records(self, session_id: str, run_id: Optional[str] = None) -> list[SessionRunRecord]:
        """输入：session_id、可选 run_id。输出：按顺序排列的 SessionRunRecord 列表。"""

        query = self.db.query(SessionRunRecord).filter(SessionRunRecord.session_id == session_id)
        if run_id is not None:
            query = query.filter(SessionRunRecord.run_id == run_id)
        return query.order_by(SessionRunRecord.created_at.asc(), SessionRunRecord.id.asc()).all()

    def list_run_events(self, run_id: str) -> list[SessionRunEventRecord]:
        """输入：run_id。输出：该次 run 的全部事件记录列表。"""

        return (
            self.db.query(SessionRunEventRecord)
            .filter(SessionRunEventRecord.run_id == run_id)
            .order_by(SessionRunEventRecord.event_index.asc(), SessionRunEventRecord.id.asc())
            .all()
        )

    def list_sessions(self) -> list[SessionRecord]:
        """输入：无。输出：按更新时间倒序排列的 SessionRecord 列表。"""

        return (
            self.db.query(SessionRecord)
            .order_by(SessionRecord.updated_at.desc(), SessionRecord.session_id.asc())
            .all()
        )

    def read_session_record(self, session_id: str) -> Optional[SessionRecord]:
        """输入：session_id。输出：SessionRecord，找不到时返回 None。"""

        return (
            self.db.query(SessionRecord)
            .filter(SessionRecord.session_id == session_id)
            .first()
        )

    def read_session_state(self, session_id: str) -> Optional[AgentState]:
        """输入：session_id。输出：反序列化后的 AgentState，找不到时返回 None。"""

        record = self.read_session_record(session_id)
        if not record:
            return None

        return AgentState.model_validate(json.loads(record.state_json))
