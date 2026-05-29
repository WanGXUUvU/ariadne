"""Run Trace 存储访问层。

职责：
- run trace 的写入与查询
- 工具调用记录的 CRUD
- 子 Agent 运行记录的管理

从 session/store.py 拆分而出，单一职责：Run 相关持久化操作。
"""

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import func as sqlfunc
from sqlalchemy.orm import Session
from agent_prototype.core.types import ChatMessage
from agent_prototype.execution.runtime.types import AgentEvent
from agent_prototype.infra.db.orm_models import (
    SessionRecord,
    SessionRunEventRecord,
    SessionRunRecord,
    ToolCallRecord,
)


class SqliteRunStore:
    """围绕 run trace 相关数据的 SQLite store。

    这个类是"运行轨迹数据仓库"。它专门负责运行记录、步骤事件和工具调用记录的读写。
    """

    def __init__(self, db: Session):
        self.db = db

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
        """保存一次完整的运行轨迹（Trace）。
        把这次运行的基本信息存入主表，然后把运行中发生的所有"事件"按顺序存入事件子表中。

        需要拿到的东西：
        - session_id (str): 属于哪个会话。
        - run_id (str): 这一轮运行的唯一 ID。
        - agent_name (str, 可选): 负责干活的 Agent 名字。
        - skill_name (str, 可选): 触发的技能名字。
        - user_input (str): 用户的输入文本。
        - reply (str): 最终给出的回复文本。
        - events (list[AgentEvent]): 运行过程中发生的所有步骤事件。

        会给出来的结果：
        - SessionRunRecord: 新建并保存好的运行记录对象。
        """

        run_record = SessionRunRecord(
            session_id=session_id,
            run_id=run_id,
            agent_name=agent_name,
            skill_name=skill_name,
            user_input=user_input,
            reply=reply,
            event_count=len(events),
            finished_at=datetime.utcnow(),
        )
        self.db.add(run_record)

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

    def save_partial_run(
        self,
        *,
        session_id: str,
        run_id: str,
        agent_name: Optional[str],
        skill_name: Optional[str],
        user_input: str,
        partial_reply: str,
        state,
        events: Optional[list] = None,
    ) -> SessionRunRecord:
        """保存"部分/未完成"的运行记录（流式输出或者中间被掐断时的保存操作）。"""
        events = events or []

        existing = self.db.query(SessionRunRecord).filter(SessionRunRecord.run_id == run_id).first()
        if existing:
            if events and existing.event_count == 0:
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
                existing.event_count = len(events)
                if partial_reply:
                    existing.reply = partial_reply
                self.db.flush()
            return existing

        run_record = SessionRunRecord(
            session_id=session_id,
            run_id=run_id,
            agent_name=agent_name,
            skill_name=skill_name,
            user_input=user_input,
            reply=partial_reply,
            event_count=len(events),
            finished_at=datetime.utcnow(),
        )
        self.db.add(run_record)

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

        if partial_reply.strip() or events:
            state.messages.append(
                ChatMessage(
                    role="assistant",
                    content=partial_reply or None,
                )
            )

        record = self.db.query(SessionRecord).filter(SessionRecord.session_id == session_id).first()
        if record:
            record.state_json = json.dumps(state.model_dump(), ensure_ascii=False)

        self.db.flush()
        return run_record

    def list_run_records(
        self, session_id: str, run_id: Optional[str] = None
    ) -> list[SessionRunRecord]:
        """列出某个会话的所有运行记录。"""
        query = self.db.query(SessionRunRecord).filter(SessionRunRecord.session_id == session_id)
        if run_id is not None:
            query = query.filter(SessionRunRecord.run_id == run_id)
        return query.order_by(SessionRunRecord.created_at.asc(), SessionRunRecord.id.asc()).all()

    def list_run_events(self, run_id: str) -> list[SessionRunEventRecord]:
        """获取某一次运行中发生的全部步骤事件。"""
        return (
            self.db.query(SessionRunEventRecord)
            .filter(SessionRunEventRecord.run_id == run_id)
            .order_by(SessionRunEventRecord.event_index.asc(), SessionRunEventRecord.id.asc())
            .all()
        )

    def append_run_events(self, *, run_id, new_events: list[AgentEvent], final_reply: str) -> None:
        """给一次运行追加新的步骤事件，并更新它的最终答复。"""
        run_record = (
            self.db.query(SessionRunRecord).filter(SessionRunRecord.run_id == run_id).first()
        )
        if not run_record:
            raise ValueError(f"run_id{run_id} not found")
        max_index = (
            self.db.query(sqlfunc.max(SessionRunEventRecord.event_index))
            .filter(SessionRunEventRecord.run_id == run_id)
            .scalar()
        )
        next_index = (max_index + 1) if max_index is not None else 0
        for event in new_events:
            event_dict = event.model_dump(exclude_none=True)
            self.db.add(
                SessionRunEventRecord(
                    run_id=run_id,
                    event_index=next_index,
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
            next_index += 1

        run_record.reply = final_reply
        run_record.event_count = (max_index + 1 if max_index is not None else 0) + len(new_events)
        run_record.run_status = "completed"
        run_record.finished_at = sqlfunc.now()

    def create_tool_call(
        self, *, run_id: str, tool_name: str, tool_call_id: Optional[str], input_json: Optional[str]
    ) -> int:
        """工具开始运行之前，创建一条工具调用记录。"""
        record = ToolCallRecord(
            run_id=run_id,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            status="running",
            input_json=input_json,
        )
        self.db.add(record)
        self.db.flush()
        return record.id

    def finish_tool_call(self, *, record_id: int, status: str, result_json: Optional[str]) -> None:
        """当一个工具跑完了，更新对应的工具调用记录。"""
        from sqlalchemy import func

        record = self.db.query(ToolCallRecord).filter(ToolCallRecord.id == record_id).first()
        if record:
            record.status = status
            record.result_json = result_json
            record.finished_at = func.now()

    def update_run_status(self, *, run_id: str, status: str) -> None:
        """更新一次运行的当前状态。"""
        from sqlalchemy import func

        self.db.flush()
        record = self.db.query(SessionRunRecord).filter(SessionRunRecord.run_id == run_id).first()
        if record:
            record.run_status = status
            if status == "completed":
                record.finished_at = func.now()

    def update_run_active(self, *, run_id: str, is_active: int) -> None:
        """设置一次运行是否为活跃状态。"""
        self.db.flush()
        record = self.db.query(SessionRunRecord).filter(SessionRunRecord.run_id == run_id).first()
        if record:
            record.is_active = str(is_active)

    def get_run_detail(self, run_id: str):
        """获取某一次运行的详细内容。"""
        run = self.db.query(SessionRunRecord).filter(SessionRunRecord.run_id == run_id).first()
        if not run:
            return None, []
        tool_calls = (
            self.db.query(ToolCallRecord)
            .filter(ToolCallRecord.run_id == run_id)
            .order_by(ToolCallRecord.id)
            .all()
        )
        return run, tool_calls

    def create_child_run(
        self,
        *,
        parent_run_id: str,
        session_id: str,
        run_id: str,
        agent_name: Optional[str],
        user_input: str,
        reply: str,
        events: list[AgentEvent],
    ) -> SessionRunRecord:
        """为子 Agent 创建一条关联的子运行记录。"""
        run_record = SessionRunRecord(
            session_id=session_id,
            run_id=run_id,
            parent_run_id=parent_run_id,
            agent_name=agent_name,
            user_input=user_input,
            reply=reply,
            event_count=len(events),
            run_status="completed",
            finished_at=datetime.utcnow(),
        )
        self.db.add(run_record)

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

    def get_children_runs(self, parent_run_id: str) -> list[SessionRunRecord]:
        """获取某个父运行下面所有派生出的子 Agent 运行记录。"""
        return (
            self.db.query(SessionRunRecord)
            .filter(SessionRunRecord.parent_run_id == parent_run_id)
            .order_by(SessionRunRecord.created_at.asc())
            .all()
        )
