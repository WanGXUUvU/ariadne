"""核心模型协议原语。

职责：
- 定义模型通信相关的消息原语、请求/响应、流式事件、适配器协议。

不负责：
- 不定义运行时状态与事件（见 execution/runtime/types.py）。
- 不定义工具执行结果（见 tools/result_types.py）。
"""

from typing import Any, AsyncIterator, Iterator, Literal, Optional, Protocol

from pydantic import BaseModel, Field


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 一、工具调用原语 — Tool Call Primitives
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ToolCallFunction(BaseModel):
    """模型返回的 function calling 结构中的函数部分。"""

    name: str
    arguments: str


class ToolCall(BaseModel):
    """一次工具调用请求。"""

    id: str
    type: Literal["function"] = "function"
    function: ToolCallFunction


class ChatMessage(BaseModel):
    """运行时消息对象，既用于上下文，也用于持久化 session state。"""

    role: Literal["system", "user", "assistant", "tool"]
    content: Optional[str] = None
    tool_calls: Optional[list[ToolCall]] = None
    tool_call_id: Optional[str] = None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 三、模型通信协议 — Model Protocol
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class ModelConfig(BaseModel):
    """一次模型调用配置"""

    model: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_output_tokens: Optional[int] = None
    stream: bool = False
    tool_choice: Optional[Any] = None
    previous_response_id: Optional[str] = None
    conversation: Optional[Any] = None
    provider_options: dict[str, Any] = Field(default_factory=dict)


class ModelRequest(BaseModel):
    """统一的模型请求对象"""

    messages: list[ChatMessage] = Field(default_factory=list)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    config: ModelConfig
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelUsage(BaseModel):
    """统一的 token 使用统计"""

    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    details: dict[str, Any] = Field(default_factory=dict)


class ModelError(BaseModel):
    """统一的模型错误结构。"""

    code: str
    message: str
    provider: Optional[str] = None
    details: dict[str, Any] = Field(default_factory=dict)


class ModelResponse(BaseModel):
    """统一的模型响应对象"""

    assistant_message: ChatMessage
    id: Optional[str] = None
    model: Optional[str] = None
    status: Literal["completed", "incomplete", "failed"] = "completed"
    finish_reason: Optional[str] = None
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

    type: str
    response_id: Optional[str] = None
    content_delta: Optional[str] = None
    thinking_delta: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None
    finish_reason: Optional[str] = None
    usage: Optional[ModelUsage] = None
    error: Optional[ModelError] = None
    raw_event: dict[str, Any] = Field(default_factory=dict)


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
        """用 async for 循环消费——每次迭代都是一个 await 点。"""
        ...
