"""SQLAlchemy ORM 模型定义。

这里描述“数据库里有哪些表、字段、关系”。
上层代码通过这些模型读写 SQLite，但不应该把 ORM 结构直接暴露给前端。
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship

from .db import Base


class SessionRecord(Base):
    """session 主表。

    存当前会话的最新快照，以及列表页需要的摘要字段。
    """

    __tablename__ = "session_records"

    session_id = Column(String, primary_key=True, index=True)
    session_name = Column(String, nullable=True)
    state_json = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    last_agent_name = Column(String, nullable=True, index=True)
    last_skill_name = Column(String, nullable=True, index=True)
    message_count = Column(Integer, nullable=False, default=0, server_default="0")
    last_reply_preview = Column(String(120), nullable=True)
    permission_profile=Column(String,nullable=False,default="conservative")


class SessionRunRecord(Base):
    """单次 run 的摘要表。

    一条记录表示某个 session 下的一次完整执行。
    """

    __tablename__ = "session_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        String,
        ForeignKey("session_records.session_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    parent_run_id = Column(String,ForeignKey("session_runs.run_id",ondelete="SET NULL"),nullable=True,index=True)
    run_id = Column(String, unique=True, nullable=False)
    run_status = Column(String,nullable=False,default="running")
    agent_name = Column(String, nullable=True, index=True)
    skill_name = Column(String, nullable=True, index=True)
    user_input = Column(Text, nullable=False)
    reply = Column(Text, nullable=False)
    event_count = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    finished_at = Column(DateTime,nullable=True)

    # `relationship()` 让 SQLAlchemy 知道父子表之间的对象关系。
    events = relationship(
        "SessionRunEventRecord",
        cascade="all,delete-orphan",
        order_by="SessionRunEventRecord.event_index",
    )

class ToolCallRecord(Base):
    __tablename__ = "tool_call_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, ForeignKey("session_runs.run_id", ondelete="CASCADE"), index=True, nullable=False)
    tool_name = Column(String, nullable=False)
    tool_call_id = Column(String, nullable=True)   # LLM 分配的 ID
    status = Column(String, nullable=False, default="running")  # running / completed / failed / timeout / cancelled
    input_json = Column(Text, nullable=True)        # 工具入参
    result_json = Column(Text, nullable=True)       # 工具结果
    started_at = Column(DateTime, server_default=func.now(), nullable=False)
    finished_at = Column(DateTime, nullable=True)   # 执行完才有

class SessionRunEventRecord(Base):
    """单次 run 下的逐条事件表。"""

    __tablename__ = "session_run_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(
        String,
        ForeignKey("session_runs.run_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    event_index = Column(Integer, nullable=False)
    type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    tool_name = Column(String, nullable=True)
    tool_call_id = Column(String, nullable=True)
    tool_result_json = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)


class AgentDefinitionRecord(Base):
    """agent 定义表。"""

    __tablename__ = "agent_definitions"

    agent_id = Column(String, primary_key=True, index=True)
    definition_json = Column(Text, nullable=False)
    update_at = Column(DateTime, server_default=func.now())
