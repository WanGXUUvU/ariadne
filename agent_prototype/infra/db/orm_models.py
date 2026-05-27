"""SQLAlchemy ORM 模型定义。

描述数据库中有哪些表、字段、关系。
上层代码通过这些模型读写 SQLite，但不应直接暴露 ORM 结构给前端。
"""

from sqlalchemy import (
    Column, DateTime, ForeignKey, Integer, JSON,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import relationship

from .engine import Base


# ── Session 相关表 ────────────────────────────────────────────────────────────

class SessionRecord(Base):
    """session 主表。存当前会话的最新快照及列表页所需摘要字段。"""

    __tablename__ = "session_records"

    session_id         = Column(String,   primary_key=True, index=True)
    session_name       = Column(String,   nullable=True)
    state_json         = Column(Text,     nullable=False)
    created_at         = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at         = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    last_agent_name    = Column(String,   nullable=True, index=True)
    last_skill_name    = Column(String,   nullable=True, index=True)
    message_count      = Column(Integer,  nullable=False, default=0, server_default="0")
    last_reply_preview = Column(String(120), nullable=True)
    permission_profile = Column(String,   nullable=False, default="conservative")
    context_tokens     = Column(Integer,  nullable=True)
    # 模型选择（NULL 表示使用环境变量 RUN_MODEL）
    model_provider_id  = Column(Integer, ForeignKey("provider_configs.id", ondelete="SET NULL"), nullable=True)
    model_id           = Column(String,   nullable=True)
    thinking_enabled   = Column(Integer,  nullable=False, default=0)   # 0/1
    thinking_effort    = Column(String,   nullable=False, default="medium")
    workspace_path     = Column(String,   nullable=True)
    workspace_name     = Column(String,   nullable=True)
    session_type       = Column(String,   nullable=False,default="coding",server_default="coding")



class SessionRunRecord(Base):
    """单次 run 的摘要表。一条记录代表某个 session 下的一次完整执行。"""

    __tablename__ = "session_runs"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    session_id  = Column(
        String,
        ForeignKey("session_records.session_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    parent_run_id = Column(
        String,
        ForeignKey("session_runs.run_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    run_id       = Column(String,   unique=True, nullable=False)
    run_status   = Column(String,   nullable=False, default="running")
    agent_name   = Column(String,   nullable=True, index=True)
    skill_name   = Column(String,   nullable=True, index=True)
    user_input   = Column(Text,     nullable=False)
    reply        = Column(Text,     nullable=False)
    event_count  = Column(Integer,  nullable=False, default=0, server_default="0")
    created_at   = Column(DateTime, server_default=func.now(), nullable=False)
    finished_at  = Column(DateTime, server_default=func.now(), nullable=False)
    is_active    = Column(String,   nullable=False,default=1,server_default="1")

    events = relationship(
        "SessionRunEventRecord",
        cascade="all,delete-orphan",
        order_by="SessionRunEventRecord.event_index",
    )


class ToolCallRecord(Base):
    """单次工具调用记录表。"""

    __tablename__ = "tool_call_records"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    run_id       = Column(String,   ForeignKey("session_runs.run_id", ondelete="CASCADE"), index=True, nullable=False)
    tool_name    = Column(String,   nullable=False)
    tool_call_id = Column(String,   nullable=True)    # LLM 分配的 ID
    status       = Column(String,   nullable=False, default="running")  # running / completed / failed / timeout / cancelled
    input_json   = Column(Text,     nullable=True)    # 工具入参
    result_json  = Column(Text,     nullable=True)    # 工具结果
    started_at   = Column(DateTime, server_default=func.now(), nullable=False)
    finished_at  = Column(DateTime, nullable=True)    # 执行完才有


class SessionRunEventRecord(Base):
    """单次 run 下的逐条事件表。"""

    __tablename__ = "session_run_events"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    run_id       = Column(
        String,
        ForeignKey("session_runs.run_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    event_index      = Column(Integer, nullable=False)
    type             = Column(String,  nullable=False)
    content          = Column(Text,    nullable=False)
    tool_name        = Column(String,  nullable=True)
    tool_call_id     = Column(String,  nullable=True)
    tool_result_json = Column(Text,    nullable=True)
    created_at       = Column(DateTime, server_default=func.now(), nullable=False)


# ── Agent 定义表 ──────────────────────────────────────────────────────────────

class AgentDefinitionRecord(Base):
    """agent 定义表。"""

    __tablename__ = "agent_definitions"

    agent_id        = Column(String,   primary_key=True, index=True)
    definition_json = Column(Text,     nullable=False)
    updated_at      = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ── 审批表 ────────────────────────────────────────────────────────────────────

class PendingApproval(Base):
    """待审批工具调用记录表。"""

    __tablename__ = "pending_approvals"

    id           = Column(String,   primary_key=True)           # UUID，审批单号
    session_id   = Column(String,   nullable=False, index=True)  # 关联 session
    run_id       = Column(String,   nullable=False)              # 关联 run
    tool_name    = Column(String,   nullable=False)              # 要执行的工具
    tool_call_id = Column(String,   nullable=True)
    arguments    = Column(Text,     nullable=False)              # 工具参数 JSON
    status       = Column(String,   nullable=False, default="pending")  # pending / approved / rejected
    created_at   = Column(DateTime, server_default=func.now(), nullable=False)
    saved_messages = Column(JSON,   nullable=False)
    event_index  = Column(Integer,  nullable=False)


# ── Provider & 模型配置表 ─────────────────────────────────────────────────────

class ProviderConfig(Base):
    """Provider 配置表。"""

    __tablename__ = "provider_configs"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    name       = Column(String,  nullable=False)
    base_url   = Column(String,  nullable=False)
    api_key    = Column(String,  nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    is_default = Column(Integer, nullable=False, default=0, server_default="0")

    models = relationship("ModelSetting", cascade="all,delete-orphan")


class ModelSetting(Base):
    """模型配置表。每行代表某 Provider 下的一个可用模型。"""

    __tablename__ = "model_settings"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    provider_id       = Column(Integer, ForeignKey("provider_configs.id", ondelete="CASCADE"), nullable=False, index=True)
    model_id          = Column(String,  nullable=False)   # 如 "deepseek-v4-flash"
    display_name      = Column(String,  nullable=True)    # 覆盖显示名
    enabled           = Column(Integer, nullable=False, default=0)  # 0/1，是否出现在对话框
    supports_thinking = Column(Integer, nullable=False, default=0)
    thinking_style    = Column(String,  nullable=True)    # "deepseek_style" | "sensenova_style" | "none"
    effort_levels     = Column(Text,    nullable=True)    # JSON 字符串，如 '["low","high"]'
    context_length    = Column(Integer, nullable=True)
    supports_tools    = Column(Integer, nullable=False, default=0)
    created_at        = Column(DateTime, server_default=func.now(), nullable=False)

    # 同一个 Provider 下，同一个 model_id 不能重复
    __table_args__ = (UniqueConstraint("provider_id", "model_id"),)


# ── 工作区表 ──────────────────────────────────────────────────────────────────

class WorkspaceRecord(Base):
    """本地已添加的项目物理工作区库。

    保存用户在机器上选择并使用过的项目物理路径，
    支持在下拉列表中快速展示、切换和删除。
    """

    __tablename__ = "workspaces"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    name       = Column(String,  nullable=False)           # 文件夹显示名称
    path       = Column(String,  nullable=False, unique=True, index=True)  # 物理绝对路径
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
