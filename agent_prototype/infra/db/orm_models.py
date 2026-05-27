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
    """session 主表。存当前会话的最新快照及列表页所需摘要字段。
    
    大白话解释：
    这是“会话大主表”。
    数据库里的这张表，就像是一个精装日记本。里面的一行记录就代表你跟 AI 的一个独立会话（Session）。它详细记录了：会话的最新快照数据（state_json）、最后一次是哪位 Agent 出了场、用到了哪个 Skill（技能）、一共发了几条消息、选择哪家大模型 Provider、当前的安全权限级别（保守还是全自动）、以及绑定了电脑上的哪个工作区文件夹。
    """

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
    """单次 run 的摘要表。一条记录代表某个 session 下的一次完整执行。
    
    大白话解释：
    这是“运行任务流水表（Run 摘要表）”。
    每次你在会话里给 AI 发送一条消息，系统就会大张旗鼓地开启一次“任务运行（Run）”。这张表就是用来给每次运行记流水的。它记录了：这次运行属于哪个会话、对应的唯一运行 ID（run_id）、这次运行现在是成功、失败还是运行中（run_status）、你发了什么、AI 回复了什么，以及它是主运行还是子运行。
    """

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
    """单次工具调用记录表。
    
    大白话解释：
    这是“工具调用流水账表”。
    AI 在单次任务运行中可能会调用好多好多个工具（比如查文件、写文件、网络检索等）。这张表就是为了帮它把每次调用工具的经过都用小本本记下来：调了哪个工具（tool_name）、喂给工具什么参数（input_json）、工具返回了什么结果（result_json）、什么时候开始调的、什么时候跑完。
    """

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
    """单次 run 下的逐条事件表。
    
    大白话解释：
    这是“步骤日志细节表（Run 事件表）”。
    在一次运行过程中，AI 的内心活动（思考思考、调用工具、出报错、输出回复等）全部会被拆解成一串有严格先后顺序的“事件”（Event）。这张表就是按步骤（event_index）把这些事件像看电影拉片一样一条条保存下来，方便前端展示精致的对话步骤轨迹。
    """

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
    """agent 定义表。
    
    大白话解释：
    这是“智能体定义表”。
    用来保存你在系统里配置的各种 Agent 人设模板（比如代码助手、翻译助手等）。只要把写好的人设 JSON 文本往 definition_json 字段里一塞，系统就能在启动时根据 agent_id 动态加载出这个小帮手。
    """

    __tablename__ = "agent_definitions"

    agent_id        = Column(String,   primary_key=True, index=True)
    definition_json = Column(Text,     nullable=False)
    updated_at      = Column(DateTime, server_default=func.now(), onupdate=func.now())


# ── 审批表 ────────────────────────────────────────────────────────────────────

class PendingApproval(Base):
    """待审批工具调用记录表。
    
    大白话解释：
    这是“待处理审批工单表”。
    专门用来存放那些被安全策略卡住的、正眼巴巴等着人类点“批准”的工具调用。它把调用 ID、工具参数（arguments）、当前会话的上下文备份（saved_messages）和步骤记录下来。人类一旦点了批准，系统就可以还原并断点续传，继续往下跑。
    """

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
    """Provider 配置表。
    
    大白话解释：
    这是“大模型供应商（Provider）配置表”。
    比如 DeepSeek、OpenAI、硅基流动等等。里面存着对接这家供应商所需的接口根地址（base_url）和极其保密的 API 密钥（api_key）。
    """

    __tablename__ = "provider_configs"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    name       = Column(String,  nullable=False)
    base_url   = Column(String,  nullable=False)
    api_key    = Column(String,  nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    is_default = Column(Integer, nullable=False, default=0, server_default="0")

    models = relationship("ModelSetting", cascade="all,delete-orphan")


class ModelSetting(Base):
    """模型配置表。每行代表某 Provider 下的一个可用模型。
    
    大白话解释：
    这是“AI模型细项配置表”。
    它是跟上面的供应商配置表连在一块的。比如供应商 DeepSeek 底下有 "deepseek-reasoner"、"deepseek-chat" 等模型。这里不仅记录了模型 ID，还细致地记录了：这个模型是否支持大模型思考（thinking）、思考风格是怎样的、支持的最大上下文 Token 长度是多少，好让对话系统做精准调度。
    """

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
    
    大白话解释：
    这是“项目文件夹登记本（工作区表）”。
    你在系统里挑过并登记好的本地电脑项目路径（例如 `/Users/yourname/my-project`），都会在这张表里留档。它能让你在前端界面下拉框里，一键轻松选择或者切换不同的开发目录。
    """

    __tablename__ = "workspaces"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    name       = Column(String,  nullable=False)           # 文件夹显示名称
    path       = Column(String,  nullable=False, unique=True, index=True)  # 物理绝对路径
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
