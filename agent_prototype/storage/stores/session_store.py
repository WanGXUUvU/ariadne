"""Session / Trace 存储访问层。

这个文件封装 SQLite 上的常用读写动作：
- session 快照的读取与更新
- run trace 的写入
- session 列表、详情、trace 的查询

上层代码尽量通过这些方法拿数据，而不是在 route / service 里直接写 ORM 查询。
"""

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session
from ...model.model_types import ModelUsage
from ...core.schemas import AgentEvent, AgentState,ChatMessage
from ..models import SessionRecord, SessionRunEventRecord, SessionRunRecord,ToolCallRecord

_UNSET=object()

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
        last_agent_name=_UNSET,
        last_skill_name=_UNSET,
        last_reply_preview=_UNSET,
        context_tokens:Optional[int]=None
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
            
            if last_agent_name is not _UNSET:
                record.last_agent_name = last_agent_name
            if last_reply_preview is not _UNSET:
                record.last_reply_preview = last_reply_preview

            record.message_count = message_count

            if last_skill_name is not _UNSET:
                record.last_skill_name = last_skill_name
            
            record.context_tokens=context_tokens
        else:
            record = SessionRecord(
                session_id=session_id,  # 新记录直接使用传入的 session_id
                session_name=session_name or session_id,  # 新建时没有名字就回退到 session_id
                state_json=state_json,  # 保存序列化后的 state
                last_agent_name=None if last_agent_name is _UNSET else last_agent_name,  # 没传就存 None，传了就按传入值存
                last_skill_name=None if last_skill_name is _UNSET else last_skill_name,  # 同理处理 skill
                message_count=message_count,  # 新记录的消息数直接来自当前 state
                last_reply_preview=None if last_reply_preview is _UNSET else last_reply_preview,  # 没传就 None，显式传 None 也还是 None
                context_tokens=context_tokens,
            )
            self.db.add(record)  # 把新建记录加入当前事务


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
            finished_at=datetime.utcnow(),
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
    
    def save_partial_run(
            self,
            *,
            session_id:str,
            run_id:str,
            agent_name:Optional[str],
            skill_name:Optional[str],
            user_input:str,
            partial_reply:str,
            state:AgentState,
            events:list = [],
    )->SessionRunRecord:
        # 用 run_id 查 run 明细表，防止重复插入同一条 run 记录
        existing=self.db.query(SessionRunRecord).filter(SessionRunRecord.run_id==run_id).first()
        if existing:
            return existing
        run_record=SessionRunRecord(
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

        # 保存第一阶段 events（工具调用、approval_required 等）
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
                        if event_dict.get("tool_result") else None
                    ),
                )
            )

        if partial_reply:
            state.messages.append(ChatMessage(role="assistant", content=partial_reply))

        record=self.db.query(SessionRecord).filter(SessionRecord.session_id==session_id).first()
        if record:
            record.state_json=json.dumps(state.model_dump(),ensure_ascii=False)

        return run_record

    def rename_session(self,session_id,new_name:str)->bool:
        """输入：session_id、新名称。输出：找到并更新返回 True，找不到返回 False。"""
        record=self.db.query(SessionRecord).filter(SessionRecord.session_id==session_id).first()
        if not record:
            return False
        record.session_name=new_name
        return True

    def delete_session(self, session_id: str) -> bool:
        """输入：session_id。输出：无，副作用是删除这个 session 的主记录。"""

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
        # 最后删 session 主记录
        self.db.delete(record)
        return True
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
    def append_run_events(self,*,run_id,new_events:list[AgentEvent],final_reply:str,)->None:
        run_record=self.db.query(SessionRunRecord).filter(SessionRunRecord.run_id==run_id).first()
        if not run_record:
            raise ValueError(f"run_id{run_id} not found")
        from sqlalchemy import func as sqlfunc
        max_index=self.db.query(sqlfunc.max(SessionRunEventRecord.event_index)).filter(SessionRunEventRecord.run_id==run_id).scalar()
        next_index =(max_index+1) if max_index is not None else 0
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

    def create_tool_call(
            self,
            *,
            run_id:str,
            tool_name:str,
            tool_call_id:Optional[str],
            input_json: Optional[str],
    )->int:
        """工具开始执行前调用。返回新建记录的id"""
        record=ToolCallRecord(
            run_id=run_id,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            status="running",
            input_json=input_json,
        )
        self.db.add(record)
        self.db.flush()
        return record.id
    
    def finish_tool_call(
            self,
            *,
            record_id:int,
            status:str,
            result_json:Optional[str]
    )->None:
        record = self.db.query(ToolCallRecord).filter(ToolCallRecord.id==record_id).first()
        if record:
            record.status=status
            record.result_json=result_json
            record.finished_at=func.now()
    
    def update_run_status(self, *, run_id: str, status: str) -> None:
        """更新 run 的状态字段。"""
        record = self.db.query(SessionRunRecord).filter(SessionRunRecord.run_id == run_id).first()
        if record:
            record.run_status = status
            if status=="completed":
                record.finished_at=func.now()

    def get_run_detail(self, run_id: str):
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
            parent_run_id:str,
            session_id:str,
            run_id:str,
            agent_name:Optional[str],
            user_input:str,
            reply:str,
            events:list[AgentEvent],
    )->SessionRunRecord:
        """输入:parent_run_id:+子run字段。输出:新建的 SessionRunRecord"""

        run_record=SessionRunRecord(
            session_id=session_id,
            run_id=run_id,
            parent_run_id=parent_run_id,
            agent_name=agent_name,
            user_input=user_input,
            reply=reply,
            event_count=len(events),
            run_status="completed",  # create_child_run 只在子 Agent 执行完后调用，直接写 completed
            finished_at=datetime.utcnow(),
        )
        self.db.add(run_record)

        for index,event in enumerate(events):
            event_dict=event.model_dump(exclude_none=True)
            self.db.add(SessionRunEventRecord(
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
            ))
        return run_record
    
    def get_children_runs(self, parent_run_id: str) -> list[SessionRunRecord]:
        """输入：parent_run_id。输出：所有子 run 记录列表。"""
        return (
            self.db.query(SessionRunRecord)
            .filter(SessionRunRecord.parent_run_id == parent_run_id)
            .order_by(SessionRunRecord.created_at.asc())
            .all()
        )