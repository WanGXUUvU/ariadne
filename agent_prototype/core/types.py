"""
[九层模型 - L1 核心领域类型层 (Core Types)]

全项目跨层共享的领域类型统一定义。

所有类型集中于此，是因为它们被 L5/L6/L7/L8 多层同时使用，
必须放在最低公共层 L1 以避免反向依赖。

仅依赖：标准库 + pydantic。本模块不依赖任何上层模块。
"""

from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Iterator, Literal, Optional, Protocol

from pydantic import BaseModel, Field


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 一、协议原语 — Tool Call Primitives
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ToolCallFunction(BaseModel):
    """模型返回的 function calling 结构中的函数部分。
    
    这是大模型发出的"函数调用具体内容数据模型"。
    它包含大模型想要调用的具体函数名（name），以及 AI 生成的想喂给函数的参数（arguments，通常是一个 JSON 字符串）。
    """

    name: str
    arguments: str


class ToolCall(BaseModel):
    """一次工具调用请求。
    
    这是大模型发出的"单次工具调用订单数据模型"。
    它记录了这笔调用的唯一身份订单 ID（id），它的调用类型（默认为 "function"），以及上面所说的具体函数调用内容。
    """

    id: str
    type: Literal["function"] = "function"
    function: ToolCallFunction


class ToolError(BaseModel):
    """工具失败时返回给上层的结构化错误。
    
    这是工具执行失败时的"结构化病历单"。
    当工具跑崩了或者出错了，它不会随地吐痰，而是很优雅地开出这张单子，写清楚：错误码是什么（code，比如 SANDBOX_VIOLATION）、调哪个工具错的（tool_name），以及具体的报错大白话原因（message）。
    """

    ok: bool = False
    code: str
    tool_name: str
    message: str


class ToolResult(BaseModel):
    """统一的工具执行结果。
    
    这是统一的"工具执行结果收据包"。
    所有的工具在执行完后，不管成功还是失败，都要把成果塞进这个结果收据包里。包里包含：有没有成功（ok）、如果成功了拿回来的正文数据（content）、如果失败了的结构化错误单（error），以及可以装任何调试元数据的百宝袋（metadata）。
    """

    ok: bool
    content: Optional[str] = None
    error: Optional[ToolError] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 二、对话消息 — Chat Message
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ChatMessage(BaseModel):
    """运行时消息对象，既用于上下文，也用于持久化 session state。
    
    这是"单条聊天消息通用模型"。
    就像微信或者 QQ 里的单条气泡消息。它记下了：这条消息是谁发的（role，可以是系统 system、用户 user、助手 assistant，或者是代表工具反馈的 tool）；消息文本内容是什么（content）；如果 AI 发出消息的同时想调工具，这里面还会带上工具订单列表（tool_calls）；如果是工具回传的结果消息，这里面还会标上对应是给哪个订单（tool_call_id）的回复。
    """

    role: Literal["system", "user", "assistant", "tool"]
    content: Optional[str] = None
    tool_calls: Optional[list[ToolCall]] = None
    tool_call_id: Optional[str] = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 三、工具风险等级 — Risk Level
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class RiskLevel(str, Enum):
    """工具风险等级。
    
    这是给工具贴的"危险指数标签"。
    - SAFE: 绝对安全（比如纯读操作、Echo测试），可以绿灯直行，不需要人类审批。
    - WRITE: 有写入操作（比如往磁盘写文件），稍微有点敏感，会根据用户的安全策略决定要不要安检拦截。
    - DANGER: 高度危险（比如网络爬虫或者修改系统配置），除非安全策略是"极度放任"，否则必须拦截并呈交人类审批。
    """
    SAFE   = "safe"    # 只读，永远不需要审批
    WRITE  = "write"   # 写操作，视策略决定
    DANGER = "danger"  # 高危，除非 never 否则都要审批


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 四、Agent 定义 — Agent Definition
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class AgentDefinition(BaseModel):
    """描述一个智能体（Agent）的"人设和超能力"配置定义。

    每个 Agent 都需要有自己独特的性格和擅长的事情。比如，这个 Agent 叫什么名字、
    它说话的语气是怎样的（系统提示词）、它身上带了哪些工具，都由这个类来统一装载和记录。
    """

    id: str = Field(default="default")
    name: str = Field(default="Default Agent")
    system_prompt: str = Field(default="你是一个助手")
    description: Optional[str] = None
    tool_names: Optional[list[str]] = None  # None 表示不限制，暴露全部工具
    is_builtin: bool = False                # True 表示来自内置 .md 文件，不可删除


# ── 内置预设定义 ──────────────────────────────────────────────────────────────

DEFAULT_AGENT_DEFINITION = AgentDefinition()

ASSISTANT_AGENT_DEFINITION = AgentDefinition(
    id="assistant",
    name="Chat Assistant",
    system_prompt=(
        "你是一个友好、简洁、诚实的通用助理。"
        "回答时直接切入要点，不确定的事情如实说明，不要编造信息。"
    ),
    description="帮助用户完成日常任务",
    tool_names=["web_search"],
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 五、运行时消息 & 状态 — Runtime Message & State
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class AgentState(BaseModel):
    """某个 session 的最新状态快照。"""

    messages: list[ChatMessage] = Field(default_factory=list)
    step: int = 0
    agent_name: Optional[str] = None


class AgentEvent(BaseModel):
    """一次 run 中的结构化事件。"""

    index: int
    type: Literal[
        "assistant_tool_call",
        "tool_result",
        "tool_error",
        "final_answer",
        "approval_required",
        "approval_result",
        "thinking",
    ]
    content: Optional[str] = None
    tool_name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_result: Optional[ToolResult] = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 六、Run 请求 & 响应 — Run I/O
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class AgentInput(BaseModel):
    """`/run` 请求体。"""

    agent_name: Optional[str] = None
    session_id: str = Field(min_length=1)
    user_input: str = Field(min_length=1)
    skill_name: Optional[str] = None


class RunMetadata(BaseModel):
    """一次 /run 的轻量元信息。"""

    session_id: str
    run_id: str = ""
    agent_name: Optional[str] = None
    skill_name: Optional[str] = None


class AgentOutput(BaseModel):
    """`/run` 响应体。"""

    reply: str
    state: AgentState
    events: list[AgentEvent]
    metadata: RunMetadata
    usage: Optional[Any] = None


class FinalizeRunInput(BaseModel):
    """内部用，run 完成时写库。"""

    user_input: str
    partial_reply: str
    agent_name: Optional[str] = None
    skill_name: Optional[str] = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 七、上下文压缩 — Compact
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CompactInput(BaseModel):
    """压缩请求参数（领域语义，非 HTTP 形状）。"""

    session_id: str = Field(min_length=1)
    trigger_threshold: int = Field(default=12, ge=1)
    keep_recent_count: int = Field(default=2, ge=1)
    force: bool = Field(default=False)


class CompactOutput(BaseModel):
    """压缩结果（领域语义，非 HTTP 形状）。"""

    state: AgentState
    did_compact: bool
    removed_count: int = 0
    compact_tokens: Optional[int] = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 八、Session 管理 — Session I/O
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class CreateSessionInput(BaseModel):
    """创建 session 的领域输入。"""

    session_name: Optional[str] = Field(default=None, min_length=1)
    workspace_path: Optional[str] = None
    workspace_name: Optional[str] = None
    session_type: Optional[str] = Field(default="coding")


class RenameSessionInput(BaseModel):
    """session 更新的领域输入。"""

    session_name: Optional[str] = None
    permission_profile: Optional[str] = None
    model_id: Optional[str] = None
    model_provider_id: Optional[int] = None
    thinking_enabled: Optional[bool] = None
    thinking_effort: Optional[str] = None
    workspace_path: Optional[str] = None
    workspace_name: Optional[str] = None


class ResetInput(BaseModel):
    """重置 session 的领域输入。"""

    session_id: str = Field(min_length=1)


class SessionSummary(BaseModel):
    """session 摘要信息（领域语义，非 HTTP 形状）。"""

    session_id: str
    session_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    last_agent_name: Optional[str] = None
    last_skill_name: Optional[str] = None
    message_count: int = 0
    last_reply_preview: Optional[str] = None
    permission_profile: str = "conservative"
    context_tokens: Optional[int] = None
    workspace_path: Optional[str] = None
    workspace_name: Optional[str] = None
    session_type: Optional[str] = Field(default="coding")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 九、模型供应商 & 模型配置 — Provider & Model Settings
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ProviderOut(BaseModel):
    """供应商领域模型（含脱敏 API Key 提示）。"""

    id: int
    name: str
    base_url: str
    api_key_hint: Optional[str] = None
    is_default: bool
    created_at: datetime


class ModelOut(BaseModel):
    """模型领域模型。"""

    id: int
    provider_id: int
    model_id: str
    display_name: str
    enabled: bool
    supports_thinking: bool
    thinking_style: str
    effort_levels: list[str]
    context_length: Optional[int]
    supports_tools: bool


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 十、模型通信协议 — Model Protocol
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ModelConfig(BaseModel):
    """一次模型调用配置"""

    model: Optional[str] = None
    temperature: Optional[float] = None  # 采样温度
    top_p: Optional[float] = None
    max_output_tokens: Optional[int] = None
    stream: bool = False
    tool_choice: Optional[Any] = None  # 工具选择策略
    previous_response_id: Optional[str] = None
    conversation: Optional[Any] = None
    provider_options: dict[str, Any] = Field(default_factory=dict)


class ModelRequest(BaseModel):
    """统一的模型请求对象"""

    messages: list[ChatMessage] = Field(default_factory=list)
    tools: list[dict[str, Any]] = Field(default_factory=list)  # 给模型看的 schema
    config: ModelConfig  # 本次调用的模型的配置
    metadata: dict[str, Any] = Field(default_factory=dict)  # 业务元数据，方便 trace 和调试


class ModelUsage(BaseModel):
    """统一的 token 使用统计"""

    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    details: dict[str, Any] = Field(default_factory=dict)  # 厂商额外的 usage 信息


class ModelError(BaseModel):
    """统一的模型错误结构。"""

    code: str  # 错误码
    message: str  # 错误信息
    provider: Optional[str] = None  # 出错的厂商
    details: dict[str, Any] = Field(default_factory=dict)


class ModelResponse(BaseModel):
    """统一的模型响应对象"""

    assistant_message: ChatMessage
    id: Optional[str] = None  # 厂商响应 id
    model: Optional[str] = None  # 返回的模型名字
    status: Literal["completed", "incomplete", "failed"] = "completed"
    finish_reason: Optional[str] = None  # 结束原因
    usage: Optional[ModelUsage] = None
    error: Optional[ModelError] = None
    raw_response: dict[str, Any] = Field(default_factory=dict)
    provider_meta: dict[str, Any] = Field(default_factory=dict)

    @property
    def content(self) -> Optional[str]:
        """上层常用正文快捷入口"""
        return self.assistant_message.content

    @property
    def tool_calls(self) -> list[ToolCall]:
        return self.assistant_message.tool_calls or []


class ModelStreamEvent(BaseModel):
    """streaming 统一事件对象"""

    type: str  # 事件类型，先保持通用
    response_id: Optional[str] = None  # 事件所属 response id
    content_delta: Optional[str] = None  # 增量文本
    thinking_delta: Optional[str] = None
    tool_call_id: Optional[str] = None  # 工具调用 id
    tool_name: Optional[str] = None  # 工具名
    finish_reason: Optional[str] = None  # 流结束原因
    usage: Optional[ModelUsage] = None  # 结束时的 usage
    error: Optional[ModelError] = None  # 流式错误信息
    raw_event: dict[str, Any] = Field(default_factory=dict)  # 原始事件，便于调试


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 十一、模型适配器协议 — Model Adapter Protocol
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ModelAdapter(Protocol):
    """大模型适配器的标准协议，约束同步/流式调用签名。"""

    def generate(self, request: ModelRequest) -> ModelResponse:
        """输入统一请求，输出统一响应"""
        ...

    def stream_generate(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        """输入统一请求，逐个 yield delta token 字符串"""
        ...

    async def async_stream_generate(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        """用 async for 循环消费——每次迭代都是一个 await 点，Python 可以在这里检查"客户端是否断开"。"""
        ...
