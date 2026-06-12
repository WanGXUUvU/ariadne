"""
[L8 执行层 - 持久化子模块类型定义]

执行层数据载体：RunContext + Run I/O 类型。
原先 AgentInput/AgentOutput/FinalizeRunInput/RunMetadata 在 core/types.py，现归位至本模块。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from agent_prototype.agent.types import AgentDefinition
from agent_prototype.core.adapters.chat_completions import ChatCompletionsAdapter
from agent_prototype.core.types import ModelUsage
from agent_prototype.execution.runtime.types import AgentEvent, AgentState
from agent_prototype.security.policy.types import ApprovalPolicy

@dataclass
class RunContext:
    """智能体单次运行所需的稳定背景物料。

    这是一份“运行前已经准备好”的静态上下文，RunLifecycle / AgentRunner
    都依赖它，但不会在执行过程中频繁重建。
    """

    # 当前会话的聊天状态快照；模型每轮推理都会以它为基础继续推进。
    state: AgentState
    # 本轮实际采用的 agent 定义，包含 system prompt 与允许调用的工具白名单。
    agent_profile: AgentDefinition
    # 已经根据 session 绑定模型解析好的大模型适配器。
    adapter: ChatCompletionsAdapter
    # 本轮工具调用所遵守的审批策略，会一路传到 tool_runner。
    approval_policy: ApprovalPolicy
    # 当前这轮真正生效的 agent 名称；用于落库、前端 metadata 和调试。
    effective_agent_name: str
    # 物理工作区路径；文件类工具最终会基于它做路径解析与 VFS 叠加。
    workspace_path: str
    # 会话类型；影响 prompt 组装、默认 agent 选择以及部分 UI/落库语义。
    session_type: str


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Run I/O
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class AgentInput(BaseModel):
    """`/run` 请求体。"""

    # 用户显式指定的 agent；为空时交给 RunContextFactory 决定默认值。
    agent_name: Optional[str] = None
    # 本轮 run 归属的 session。
    session_id: str = Field(min_length=1)
    # 用户本轮输入的原始文本。
    user_input: str = Field(min_length=1)
    # 可选的 skill 名称，仅作为元信息向下游透传。
    skill_name: Optional[str] = None
    # 前端显式传入的工作区路径；当前主链仍以 session 绑定的 workspace 为准。
    workspace_path: Optional[str] = None


class RunMetadata(BaseModel):
    """一次 /run 的轻量元信息。"""

    session_id: str
    run_id: str = ""
    agent_name: Optional[str] = None


class AgentOutput(BaseModel):
    """`/run` 响应体。"""

    reply: str
    state: AgentState
    events: list
    metadata: RunMetadata
    usage: Optional[Any] = None


class FinalizeRunInput(BaseModel):
    """内部用，run 完成时写库。"""

    user_input: str
    reply_text: str
    agent_name: Optional[str] = None

class RunFinalStatus(str, Enum):
    """一次 run 的统一终态。"""

    COMPLETED = "completed"
    PAUSED = "paused"
    CANCELLED = "cancelled"
    FAILED = "failed"


class RunFinalizationInput(BaseModel):
    """统一的 run 终态收口输入。

    RunLifecycle 不直接关心“怎么写库、怎么处理 VFS”，
    它只在结束时把这张终态收口单交给 RunRecorder。
    """

    # 这次 run 属于哪个 session。
    session_id: str
    # 这次 run 的唯一 ID，也是 VFS / trace / approval 的关联键。
    run_id: str
    # 这次 run 最终以什么状态结束。
    status: RunFinalStatus
    # 当前 run 对应的用户输入；中断/失败场景补 user message 时要用。
    user_input: str
    # 最终完整 reply，或者中断时的 partial reply。
    reply_text: str
    # 本轮实际执行的 agent 名称；用于 run 摘要和 session 元数据。
    agent_name: Optional[str] = None
    # 本轮正式事件账本；注意不包含所有过程噪音，例如 tool_progress。
    events: list[AgentEvent] = Field(default_factory=list)
    # 本轮结束时的最新状态快照。
    state: AgentState = Field(default_factory=AgentState)
    # 模型用量；只有支持用量统计的适配器才会提供。
    usage: Optional[ModelUsage] = None
    # 会话类型，会影响 session snapshot 的落库字段。
    session_type: str = "coding"
    # True 表示往已有 run 追加事件（典型是 resume），False 表示新建一条完整 run trace。
    append_events: bool = False
    # 控制这次终态收口是否更新主 session snapshot；child run 会显式关掉。
    update_session_snapshot: bool = True
