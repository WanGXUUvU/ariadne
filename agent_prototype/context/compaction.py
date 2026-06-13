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
from agent_prototype.core.types import ChatMessage, ModelAdapter, ModelRequest, ModelConfig
from agent_prototype.execution.runtime.types import RunState
from agent_prototype.memory.summary.types import CompactOutput

DEFAULT_COMPACT_THRESHOLD = 12  # 默认超过12条消息时触发 compact
DEFAULT_KEEP_RECENT_COUNT = 4  # 默认 compact 后保留最近 4 条原始消息

COMPACT_SUMMARY_PREFIX = (  # 定义 compact summary 的固定前缀，明确告诉模型这不是逐字历史
    "[COMPACT_SUMMARY]\n"
    "The following is a compressed summary of the middle part of the conversation. "  # 说明下面是中段压缩摘要
    "It is not a verbatim transcript. "  # 明确声明这不是逐字记录
    "Preserve task goals, constraints, important tool results, and unfinished work."  # 要求保留目标、约束、工具结果和未完成事项
)


def split_messages_for_compaction(
    messages: list[ChatMessage],  # 输入完整历史消息列表
    keep_recent_count: int = DEFAULT_KEEP_RECENT_COUNT,  # 输入要保留的最近原始消息数量
) -> tuple[list[ChatMessage], list[ChatMessage], list[ChatMessage]]:
    """把一长串的历史聊天记录切成三段：开头（前锚点）、中间（准备被压扁压缩的一段）和结尾（最近发生的、原样保留的几条）。
    这样我们就知道要把哪部分送去让大模型压缩了。

    需要拿到的东西：
    - messages: 完整的历史聊天消息列表。
    - keep_recent_count: 结尾需要原样保留、不被压缩的消息数量。

    会给出来的结果：
    - 一个有三个元素的元组，分别是：(前锚点消息列表, 中间待压缩消息列表, 最近的原始消息列表)。
    """

    if not messages:
        return [], [], []

    anchor_messages = [messages[0]]
    remaining_messages = messages[1:]

    if len(remaining_messages) <= keep_recent_count:
        return anchor_messages, [], remaining_messages

    middle_messages = remaining_messages[
        :-keep_recent_count
    ]  # 去掉最后 recent 后，中间这段就是要压缩的主体
    recent_messages = remaining_messages[-keep_recent_count:]  # 最后几条消息作为 recent 原样保留

    return anchor_messages, middle_messages, recent_messages


def build_compact_prompt(middle_messages: list[ChatMessage]) -> str:
    """专门为大模型准备一个“压缩指令”！把中间那段长长的聊天记录整理一下，
    加上提示词，做成一个任务书，拜托大模型帮我们把这段内容归纳总结一下。

    需要拿到的东西：
    - middle_messages: 需要被压缩的中间那段聊天记录列表。

    会给出来的结果：
    - 一大段文本（Prompt），直接拿去喂给大模型就行。
    """

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
            tool_names = ",".join(
                tc.function.name for tc in message.tool_calls
            )  # 只记录工具名，不展开参数
            lines.append(f"- assistant 调用了工具: {tool_names}")
            continue
        content = message.content or "(空)"
        lines.append(f"- {message.role}: {content}")

    lines.append("")  # 空一行提升可读性
    lines.append("请直接输出摘要，语言与对话保持一致，不要重复上面的指令：")

    return "\n".join(lines)


def build_compact_summary_message(summary_text: str) -> ChatMessage:
    """大模型写好摘要文本后，这个函数会把文本包装成一条系统（system）消息，
    并在开头贴上一个标签，告诉大家：“注意啦，下面是之前聊天中段的压缩版摘要！”

    需要拿到的东西：
    - summary_text: 大模型总结出来的摘要纯文本。

    会给出来的结果：
    - 一个 ChatMessage 消息对象，格式完美，可以直接存进聊天历史里。
    """

    return ChatMessage(
        role="system",  # 用 system 角色，表示这是系统注入的 compact 摘要，不是 assistant 原话
        content=f"{COMPACT_SUMMARY_PREFIX}\n\n{summary_text.strip()}",  # 把固定前缀 and 模型返回正文拼成最终摘要消息内容
    )


def compact_state_with_summary(
    state: RunState,  # 输入当前完整会话状态
    summary_text: str,  # 输入模型已经完整好的 compact 摘要文本
    keep_recent_count: int = DEFAULT_KEEP_RECENT_COUNT,
) -> CompactOutput:
    """真正动手把历史聊天状态里的“中段”替换成大模型写好的“压缩摘要”！
    它会检查如果中段消息其实很少就懒得压缩了；如果确实压缩了，就组装出一个全新的状态，并数数这次帮用户省下了多少条消息。

    需要拿到的东西：
    - state: 当前未压缩的完整智能体状态。
    - summary_text: 已经生成好的中段摘要文本。
    - keep_recent_count: 结尾要保留几条原样消息。

    会给出来的结果：
    - 一个 CompactOutput 对象，里面包含了：压缩后的新状态、到底有没有真的进行压缩（布尔值）、以及一共删掉了多少条原始消息。
    """

    anchor_messages, middle_messages, recent_messages = (
        split_messages_for_compaction(  # 把历史切成三段
            state.messages,  # 传入原始消息列表
            keep_recent_count=keep_recent_count,  # 把 recent 保留数量传进去
        )
    )

    summary_message = build_compact_summary_message(summary_text)
    compacted_messages = anchor_messages + [summary_message] + recent_messages
    compacted_state = state.model_copy(
        update={"messages": compacted_messages}
    )  # 基于旧 state 复制一个只替换 messages 的新 state

    return CompactOutput(
        state=compacted_state,  # 返回 compact 后的新状态
        did_compact=True,  # 标记这次确实发生了 compact
        removed_count=len(state.messages)- len(compacted_messages),  # 计算这次一共折叠掉了多少条原始消息
    )


class HistoryCompactor:
    """这是一个“历史记录压缩调度员”。
    它的工作是协调大模型适配器（ModelAdapter），把对话历史中太长太旧的中间部分，
    让大模型给精简压缩成一句话摘要，以便腾出更多上下文空间，不让大模型“忘事”或者超出字数限制。
    """

    def __init__(self, adapter: ModelAdapter):
        """初始化压缩调度员，给他配备一个跟大模型沟通的“传声筒”（ModelAdapter）。

        需要拿到的东西：
        - adapter: 模型适配器，用来向大模型发请求。
        """
        self.adapter = adapter
        self.last_compact_tokens: Optional[int] = None

    def compact(self, messages: list[ChatMessage], keep_recent: int) -> str:
        """调度员的核心工作：挑出消息里能压缩的中间部分，拼好任务提示词发送给大模型，拿到大模型回复的摘要并返回。

        需要拿到的东西：
        - messages: 原始的所有消息列表。
        - keep_recent: 结尾要保留的消息数量。

        会给出来的结果：
        - 压缩好的摘要纯文本字符串（如果没东西可压，就返回空字符串）。
        """
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
