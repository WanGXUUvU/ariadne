"""
[九层模型 - L6 上下文压缩层 (Context Compaction Layer)]

文件职责：
- 定义历史对话压缩格式（前锚点、中段要压缩内容、最近保留原始消息）。
- 落地 `HistoryCompactor` 大模型历史压缩总调度器，专门通过 LLM API 获取中段消息摘要。
- 封装生成标准 `[COMPACT_SUMMARY]` 消息气泡并执行 state 响应式替换的算法。

上游依赖：L5 记忆层 (CompactService)。
下游依赖：L1 模型层 (ModelAdapter)。
"""
from typing import Optional
from agent_prototype.model.types.domain import ChatMessage
from agent_prototype.api.dto.schemas import AgentState, CompactOutput
from agent_prototype.model.adapters.protocol import ModelAdapter
from agent_prototype.model.types.model_types import ModelRequest, ModelConfig

DEFAULT_COMPACT_THRESHOLD=12 #默认超过12条消息时触发 compact
DEFAULT_KEEP_RECENT_COUNT=4 #默认 compact 后保留最近 4 条原始消息

COMPACT_SUMMARY_PREFIX = (  # 定义 compact summary 的固定前缀，明确告诉模型这不是逐字历史
    "[COMPACT_SUMMARY]\n"
    "The following is a compressed summary of the middle part of the conversation. "  # 说明下面是中段压缩摘要
    "It is not a verbatim transcript. "  # 明确声明这不是逐字记录
    "Preserve task goals, constraints, important tool results, and unfinished work."  # 要求保留目标、约束、工具结果和未完成事项
)

def split_messages_for_compaction(
        messages:list[ChatMessage], #输入完整历史消息列表
        keep_recent_count:int=DEFAULT_KEEP_RECENT_COUNT, #输入要保留的最近原始消息数量
)->tuple[list[ChatMessage],list[ChatMessage],list[ChatMessage]]:
    """输入：完整消息列表。 输出：前锚点、中段、最近消息。""" #这个函数值负责切分 不负责调用模型

    if not messages:
        return [],[],[]
    
    anchor_messages = [messages[0]]
    remaining_messages = messages[1:]

    if len(remaining_messages) <= keep_recent_count:
        return anchor_messages,[],remaining_messages
    
    middle_messages = remaining_messages[:-keep_recent_count]  # 去掉最后 recent 后，中间这段就是要压缩的主体
    recent_messages = remaining_messages[-keep_recent_count:]  # 最后几条消息作为 recent 原样保留

    return anchor_messages,middle_messages,recent_messages

def build_compact_prompt(middle_messages:list[ChatMessage])->str:
    """输入：中段消息。输出：发给模型的 compact prompt。"""

    lines = [
        "你是一个对话历史压缩助手。",
        "请将以下对话片段的核心内容压缩成简洁的摘要。",
        "要求：",
        "- 保留关键任务目标、重要约束、工具调用结果和未完成的工作",
        "- 直接输出摘要内容，不要在摘要中包含 [COMPACT_SUMMARY] 标签或任何说明前缀",
        "- 使用简洁流畅的语言，避免多余格式",
        "",
        "需要压缩的对话片段：",
    ]

    for message in middle_messages:
        if message.tool_calls:
            tool_names = ",".join(tc.function.name for tc in message.tool_calls)  # 只记录工具名，不展开参数
            lines.append(f"- assistant 调用了工具: {tool_names}")
            continue
        content = message.content or "(空)"
        lines.append(f"- {message.role}: {content}")

    lines.append("")  # 空一行提升可读性
    lines.append("请直接输出摘要，语言与对话保持一致，不要重复上面的指令：")

    return "\n".join(lines)

def build_compact_summary_message(summary_text: str) -> ChatMessage:
    """输入：模型返回的 summary 文本。输出：可回写到 state 的 summary message。"""  # 这个函数负责把文本包装成一条 ChatMessage

    return ChatMessage(
        role="system",  # 用 system 角色，表示这是系统注入的 compact 摘要，不是 assistant 原话
        content=f"{COMPACT_SUMMARY_PREFIX}\n\n{summary_text.strip()}",  # 把固定前缀 and 模型返回正文拼成最终摘要消息内容
    )

def compact_state_with_summary( 
        state:AgentState, #输入当前完整会话状态
        summary_text:str, #输入模型已经完整好的 compact 摘要文本
        keep_recent_count:int=DEFAULT_KEEP_RECENT_COUNT,
)->CompactOutput:
    """输入：原 state、summary 文本。输出：compact 后的新状态。"""  # 这个函数不负责调模型，把原本的messages中间的部分替换成总结好的

    anchor_messages,middle_messages,recent_messages = split_messages_for_compaction(#把历史切成三段
        state.messages, #传入原始消息列表
        keep_recent_count=keep_recent_count, #把 recent 保留数量传进去
    )

    if len(middle_messages) < 2:  # 中段消息少于 2 条时，内容太短，没有压缩价值，直接跳过
        return CompactOutput(state=state,did_compact=False,removed_count=0) #说明这次不需要 compact 原样返回
    
    summary_message = build_compact_summary_message(summary_text)
    compacted_messages = anchor_messages + [summary_message] + recent_messages
    compacted_state = state.model_copy(update={"messages": compacted_messages})  # 基于旧 state 复制一个只替换 messages 的新 state

    return CompactOutput(
        state=compacted_state,  # 返回 compact 后的新状态
        did_compact=True,  # 标记这次确实发生了 compact
        removed_count=len(state.messages) - len(compacted_messages),  # 计算这次一共折叠掉了多少条原始消息
    )


class HistoryCompactor:
    """历史压缩总调度器 (L6 上下文层)。
    
    职责：
    通过组合 L1 ModelAdapter 进行有损的历史摘要请求，生成摘要字符串。
    """

    def __init__(self, adapter: ModelAdapter):
        self.adapter = adapter
        self.last_compact_tokens: Optional[int] = None

    def compact(self, messages: list[ChatMessage], keep_recent: int) -> str:
        """调用 LLM 生成中段摘要文本，返回摘要字符串。"""
        _, middle_messages, _ = split_messages_for_compaction(
            messages,
            keep_recent_count=keep_recent,
        )
        if not middle_messages:
            self.last_compact_tokens = None
            return ""

        compact_prompt = build_compact_prompt(middle_messages)
        request = ModelRequest(
            messages=[
                ChatMessage(role="system", content=compact_prompt),
            ],
            tools=[],
            config=ModelConfig(stream=False),
            metadata={"mode": "compact"},
        )
        summary_response = self.adapter.generate(request)
        
        if summary_response.usage and summary_response.usage.input_tokens:
            self.last_compact_tokens = summary_response.usage.input_tokens
        else:
            self.last_compact_tokens = None

        return (summary_response.content or "").strip()