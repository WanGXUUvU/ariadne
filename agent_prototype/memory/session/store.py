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
from agent_prototype.model.types.model_types import ModelUsage
from agent_prototype.api.dto.schemas import AgentEvent, AgentState,ChatMessage
from agent_prototype.infra.db.orm_models import SessionRecord, SessionRunEventRecord, SessionRunRecord, ToolCallRecord

_UNSET=object()

class SqliteSessionStore:
    """围绕 session 相关数据的 SQLite store。
    
    这个类是“会话数据仓库”。它就像是直接在数据库里干脏活累活的底层工人，专门负责具体的数据读取和写入。比如：往数据库存入聊天历史的快照、记录每一次运行轨迹、帮上层查询会话列表、记下工具（Tool）被调用的过程等。
    """

    def __init__(self, db: Session):
        """数据仓库初始化，拿好操作数据库的“钥匙”。

        需要拿到的东西：
        - db (Session): 数据库会话连接。
        """
        self.db = db

    def get(self, session_id: str) -> Optional[AgentState]:
        """获取一个会话当前的聊天状态。

        需要拿到的东西：
        - session_id (str): 会话 ID。

        会给出来的结果：
        - Optional[AgentState]: 会话的状态（比如存了哪些聊天消息），要是找不到就返回 None。
        """

        return self.read_session_state(session_id)

    def upsert_session_snapshot(
        self,
        session_id: str,
        state: AgentState,
        session_name: Optional[str] = None,
        last_agent_name=_UNSET,
        last_skill_name=_UNSET,
        last_reply_preview=_UNSET,
        context_tokens:Optional[int]=None,
        workspace_path=_UNSET,
        workspace_name =_UNSET,
        session_type=_UNSET,
    ) -> SessionRecord:
        """保存或更新会话的“快照”（也就是当前的聊天状态和相关信息）。
        "upsert" 的意思是：如果数据库里已经有这个会话，那就把最新的消息和参数更新进去；如果没有，那就创建一个新的会话记录存起来。

        需要拿到的东西：
        - session_id (str): 会话 ID。
        - state (AgentState): 当前会话的聊天状态对象。
        - session_name (str, 可选): 会话的名字。
        - last_agent_name (可选): 上一次说话的 Agent 名字。
        - last_skill_name (可选): 上一次使用的技能名字。
        - last_reply_preview (可选): 上一次回复内容的预览。
        - context_tokens (int, 可选): 上下文消耗 of Token 数量。
        - workspace_path (可选): 工作空间绝对路径。
        - workspace_name (可选): 工作空间名字。
        - session_type (可选): 会话类型。

        会给出来的结果：
        - SessionRecord: 保存或更新后的数据库 SessionRecord 记录对象。
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
            if workspace_name is not _UNSET:
                record.workspace_name=workspace_name
            if workspace_path is not _UNSET:
                record.workspace_path=workspace_path
            if session_type is not _UNSET:
                record.session_type = session_type
            record.context_tokens=context_tokens
        else:
            record = SessionRecord(
                session_id=session_id,  # 新记录直接使用传入 the session_id
                session_name=session_name or session_id,  # 新建时没有名字就回退到 session_id
                state_json=state_json,  # 保存序列化后的 state
                last_agent_name=None if last_agent_name is _UNSET else last_agent_name,  # 没传就存 None，传了就按传入值存
                last_skill_name=None if last_skill_name is _UNSET else last_skill_name,  # 同理处理 skill
                message_count=message_count,  # 新记录的消息数直接来自当前 state
                last_reply_preview=None if last_reply_preview is _UNSET else last_reply_preview,  # 没传就 None，显式传 None 也还是 None
                context_tokens=context_tokens,
                workspace_path=None if workspace_path is _UNSET else workspace_path,
                workspace_name=None if workspace_name is _UNSET else workspace_name,
                session_type="coding" if session_type is _UNSET else session_type,
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
        """保存一次完整的运行轨迹（Trace）。
        把这次运行的基本信息（比如哪个 Agent 在干活、干了什么、用户的提问是什么、助手的最终回复是什么）存入主表，然后把运行中发生的所有“事件”（比如调用了什么工具、吐出了什么中间文本）按顺序存入事件子表中。

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
        """保存“部分/未完成”的运行记录（流式输出或者中间被掐断时的保存操作）。
        如果这次运行记录在数据库里已经存在了，就把新的事件补进去；如果还没有，就建一条新的。并且还会顺便把当前的中间聊天状态写进会话主表中。

        需要拿到的东西：
        - session_id (str): 属于哪个会话。
        - run_id (str): 这一轮运行的唯一 ID。
        - agent_name (str, 可选): 负责干活的 Agent 名字。
        - skill_name (str, 可选): 触发的技能名字。
        - user_input (str): 用户的输入文本。
        - partial_reply (str): 目前吐出来的部分回复。
        - state (AgentState): 当前会话的聊天状态。
        - events (list): 运行过程中到目前为止的所有步骤事件。

        会给出来的结果：
        - SessionRunRecord: 创建或更新后的运行记录对象。
        """
        # 用 run_id 查 run 明细表，防止重复插入同一条 run 记录
        existing=self.db.query(SessionRunRecord).filter(SessionRunRecord.run_id==run_id).first()
        if existing:
            # finalize_run 可能已抢先建了空记录（events=[]）；
            # SSE finally 块稍后带着真实 events 再次调用时，补入事件而不是直接返回。
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
                                if event_dict.get("tool_result") else None
                            ),
                        )
                    )
                existing.event_count = len(events)
                if partial_reply:
                    existing.reply = partial_reply
                self.db.flush()
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

        # 只要本次 run 产生了任何内容（文字或过程事件），就写入 assistant 消息作为锚点。
        # thinking 途中终止时 partial_reply="" 但 events 非空，同样需要写入，
        # 否则刷新后 loadSessionDetail 找不到 assistant 消息，无法挂 timeline。
        # 注意：partial_reply.strip() 过滤纯空白字符串（模型刚吐出换行就被 Stop），
        # 防止写入无意义的 assistant 锚点，导致刷新后出现重复消息卡片。
        if partial_reply.strip() or events:
            state.messages.append(ChatMessage(
                role="assistant",
                content=partial_reply or None,
            ))

        record=self.db.query(SessionRecord).filter(SessionRecord.session_id==session_id).first()
        if record:
            record.state_json=json.dumps(state.model_dump(),ensure_ascii=False)

        self.db.flush()

        return run_record

    def rename_session(self,session_id,new_name:str)->bool:
        """在数据库里给指定会话改名。

        需要拿到的东西：
        - session_id: 要改名的会话 ID。
        - new_name (str): 新的名字。

        会给出来的结果：
        - bool: 如果改名成功返回 True，如果没找到这个会话返回 False。
        """
        record=self.db.query(SessionRecord).filter(SessionRecord.session_id==session_id).first()
        if not record:
            return False
        record.session_name=new_name
        return True

    def delete_session(self, session_id: str) -> bool:
        """在数据库里彻底把一个会话连根拔除。
        除了删掉会话主记录，还会把该会话对应的所有运行历史记录、步骤事件、工具调用记录通通一并清空，绝不留任何无用数据。

        需要拿到的东西：
        - session_id (str): 准备删除的会话 ID。

        会给出来的结果：
        - bool: 找到并删除成功返回 True，如果找不到该会话返回 False。
        """

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
        """列出某个会话的所有运行记录。可以用来还原聊天流逝的轨迹或者单独查某一轮运行。

        需要拿到的东西：
        - session_id (str): 会话 ID。
        - run_id (str, 可选): 如果传了，就只查这一个特定的运行记录。

        会给出来的结果：
        - list[SessionRunRecord]: 按时间从早到晚排序的运行记录列表。
        """

        query = self.db.query(SessionRunRecord).filter(SessionRunRecord.session_id == session_id)
        if run_id is not None:
            query = query.filter(SessionRunRecord.run_id == run_id)
        return query.order_by(SessionRunRecord.created_at.asc(), SessionRunRecord.id.asc()).all()

    def list_run_events(self, run_id: str) -> list[SessionRunEventRecord]:
        """获取某一次运行中发生的全部步骤事件（比如先调用了文件读取工具，又进行了安全审查，最后吐出思考）。

        需要拿到的东西：
        - run_id (str): 运行 ID。

        会给出来的结果：
        - list[SessionRunEventRecord]: 按步骤发生顺序排列的事件记录列表。
        """

        return (
            self.db.query(SessionRunEventRecord)
            .filter(SessionRunEventRecord.run_id == run_id)
            .order_by(SessionRunEventRecord.event_index.asc(), SessionRunEventRecord.id.asc())
            .all()
        )

    def append_run_events(self,*,run_id,new_events:list[AgentEvent],final_reply:str,)->None:
        """给一次正在进行或已经告一段落的运行追加新的步骤事件，并更新它的最终答复。

        需要拿到的东西：
        - run_id: 运行 ID。
        - new_events (list[AgentEvent]): 要追加的事件列表。
        - final_reply (str): 这次运行最终的回复内容。
        """
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
        """获取数据库中所有的会话列表，用来在界面左侧侧边栏展示。

        会给出来的结果：
        - list[SessionRecord]: 会话记录列表，按照最近更新时间倒序排列（越新活跃的越排在前面）。
        """

        return (
            self.db.query(SessionRecord)
            .order_by(SessionRecord.updated_at.desc(), SessionRecord.session_id.asc())
            .all()
        )

    def read_session_record(self, session_id: str) -> Optional[SessionRecord]:
        """根据会话 ID 查出它在数据库里的主记录对象。

        需要拿到的东西：
        - session_id (str): 会话 ID。

        会给出来的结果：
        - Optional[SessionRecord]: 对应的会话主记录，没找到就返回 None。
        """

        return (
            self.db.query(SessionRecord)
            .filter(SessionRecord.session_id == session_id)
            .first()
        )

    def read_session_state(self, session_id: str) -> Optional[AgentState]:
        """读取并反序列化一个会话的完整聊天状态（包含历史消息列表等）。因为数据库里存的是一串 JSON 文本，这里会把它转换回方便 Python 代码直接操作的 `AgentState` 对象。

        需要拿到的东西：
        - session_id (str): 会话 ID。

        会给出来的结果：
        - Optional[AgentState]: 反序列化出来的聊天状态对象，找不到这个会话时返回 None。
        """

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
        """工具开始运行之前，在数据库中创建一条“工具调用记录”。用来记录哪个工具在什么时间开始跑、喂给它的输入参数是什么。

        需要拿到的东西：
        - run_id (str): 属于哪次运行。
        - tool_name (str): 跑的工具叫什么名字。
        - tool_call_id (str, 可选): 工具调用的唯一 ID 标识。
        - input_json (str, 可选): 喂给工具的参数的 JSON 字符串。

        会给出来的结果：
        - int: 刚刚在数据库里创建的那条工具调用记录的自增 ID。
        """
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
        """当一个工具跑完了（无论成功还是失败），更新对应的工具调用记录。把状态改成“成功”或“失败”，并记下吐出来的结果和结束时间。

        需要拿到的东西：
        - record_id (int): 要更新的工具调用记录的 ID（就是 create_tool_call 返回的那个数字）。
        - status (str): 执行状态（例如 "success" 成功, "failed" 失败）。
        - result_json (str, 可选): 工具吐出来的结果的 JSON 字符串。
        """
        record = self.db.query(ToolCallRecord).filter(ToolCallRecord.id==record_id).first()
        if record:
            record.status=status
            record.result_json=result_json
            record.finished_at=func.now()
    
    def update_run_status(self, *, run_id: str, status: str) -> None:
        """更新一次运行（Run）的当前状态。比如从“运行中”更新为“已完成”。

        需要拿到的东西：
        - run_id (str): 运行 ID。
        - status (str): 新的状态。
        """
        self.db.flush()
        record = self.db.query(SessionRunRecord).filter(SessionRunRecord.run_id == run_id).first()
        if record:
            record.run_status = status
            if status=="completed":
                record.finished_at=func.now()
    
    def update_run_active(self, *, run_id: str, is_active: int) -> None:
        """设置一次运行是否为活跃状态。

        需要拿到的东西：
        - run_id (str): 运行 ID。
        - is_active (int): 1 表示活跃，0 表示不活跃。
        """
        self.db.flush()
        record = self.db.query(SessionRunRecord).filter(SessionRunRecord.run_id == run_id).first()
        if record:
            record.is_active = str(is_active)

    def reset_session_runs(self, session_id: str) -> None:
        """把某个会话下的所有核心运行记录全部标记为“非活跃”（即 `is_active = 0`），表示聊天被重置，这一批记录成为了历史轨迹。

        需要拿到的东西：
        - session_id (str): 会话 ID。
        """
        self.db.query(SessionRunRecord).filter(
            SessionRunRecord.session_id == session_id,
            SessionRunRecord.parent_run_id == None
        ).update({"is_active": "0"}, synchronize_session=False)

    def get_run_detail(self, run_id: str):
        """获取某一次运行的详细内容，包括这次运行的主记录，以及在这次运行里发生的所有工具调用记录。

        需要拿到的东西：
        - run_id (str): 运行 ID。

        会给出来的结果：
        - tuple: (运行主记录, 工具调用记录列表)。如果没找到对应的运行，会返回 (None, [])。
        """
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
        """为“子 Agent”（就是大 Agent 派生出去干活的辅助小助手）创建一条关联的子运行记录，并把它跟父级运行 ID 绑定。同时把小助手执行时发生的所有事件按顺序写进事件子表中。

        需要拿到的东西：
        - parent_run_id (str): 父级（大 Agent）的运行 ID。
        - session_id (str): 属于哪个会话。
        - run_id (str): 子运行的 ID。
        - agent_name (str, 可选): 子 Agent 的名字。
        - user_input (str): 派给子 Agent 的任务输入。
        - reply (str): 子 Agent 执行完毕后交差的结果。
        - events (list[AgentEvent]): 子 Agent 执行期间产生的所有事件。

        会给出来的结果：
        - SessionRunRecord: 新建并保存好的子运行记录对象。
        """

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
        """获取某个父运行下面所有派生出的子 Agent 运行记录。

        需要拿到的东西：
        - parent_run_id (str): 父级运行 ID。

        会给出来的结果：
        - list[SessionRunRecord]: 子运行记录列表，按时间先后顺序排列。
        """
        return (
            self.db.query(SessionRunRecord)
            .filter(SessionRunRecord.parent_run_id == parent_run_id)
            .order_by(SessionRunRecord.created_at.asc())
            .all()
        )