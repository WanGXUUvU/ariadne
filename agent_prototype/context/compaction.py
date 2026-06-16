"""
[九层模型 - L6 上下文压缩层 (Context Compaction Layer)]

文件职责：
- 定义历史对话压缩格式。
- 落地 `HistoryCompactor` 大模型历史压缩总调度器，专门通过 LLM API 获取全量历史摘要。
- 封装生成标准 `[COMPACT_SUMMARY]` 消息气泡并执行 state 响应式替换的算法。

上游依赖：L5 记忆层 (CompactService)。
下游依赖：L1 模型层 (ModelAdapter)。
"""

import re
from dataclasses import dataclass
from typing import Optional

from agent_prototype.core.types import (
    ChatMessage,
    ModelAdapter,
    ModelRequest,
    ModelConfig,
)

COMPACT_SUMMARY_PREFIX = (
    "[COMPACT_SUMMARY]\n"
    "这是一份结构化上下文摘要，用于替代压缩前的完整对话历史。"
    "后续模型应把它视为继续执行任务的权威上下文。"
    "除非摘要中明确标注为逐字引用，否则它不是原始对话逐字记录。"
)

NO_TOOLS_PREAMBLE = """你现在处于上下文压缩模式。
你没有任何工具可用。
不要尝试调用读取文件、执行命令、搜索、访问外部系统等任何工具。
如果你认为需要额外信息，请只基于当前对话中已经出现的信息完成压缩。
只按下面要求输出压缩结果，不要输出额外说明。"""

BASE_COMPACT_PROMPT = """你的任务是为当前对话生成一份结构化、足够详细的上下文摘要。
这份摘要会替代压缩前的完整对话历史，用来节省上下文空间，
同时必须保留后续继续执行任务所需的全部关键信息。

你必须包含下面 9 个部分。请把分析过程写在 <analysis> 标签内，
把最终摘要写在 <summary> 标签内。

<analysis>
请逐步分析：
1. 用户最初的目标是什么，后续又补充或修正了哪些要求？
2. 对话中出现了哪些重要对象、文件、接口、数据、代码片段、错误或处理结果？
3. 哪些事项已经完成，哪些事项仍未完成？
4. 压缩发生前，当前任务正处于什么准确状态？
</analysis>

<summary>
1. PRIMARY REQUEST AND INTENT:
   （说明用户的原始目标，以及后续对目标的补充、收窄或修正。要具体。）

2. KEY TECHNICAL CONCEPTS:
   （列出对继续任务有用的关键概念、术语、架构决策、业务规则、工具能力或约束。）

3. FILES AND CODE SECTIONS:
   （如果对话涉及文件、代码、接口、数据结构或配置，请列出路径/名称和关键内容。
    如有必要，包含精确代码片段或行号；如果不涉及代码，也要说明相关对象或数据。）

4. ERRORS AND FIXES:
   （列出遇到的错误、误解、失败尝试、根因和最终处理方式。）

5. PROBLEM SOLVING:
   （说明已经解决的问题、采用的推理或权衡，以及仍在调查或需要继续判断的点。）

6. ALL USER MESSAGES:
   （逐字引用用户发送过的每一条消息。不要改写，不要概括。）

7. PENDING TASKS:
   （列出用户明确要求但尚未完成的事项。）

8. CURRENT WORK STATE:
   （准确描述压缩发生前的当前状态，例如：刚完成某项修改、正在等待验证、
    正准备继续某个步骤、或已经没有未完成工作。）

9. OPTIONAL NEXT STEP SUGGESTION:
   （基于当前对话给出一个具体下一步建议。
    必须引用用户或助手的原文来说明为什么建议这一步。）
</summary>"""


@dataclass
class CompactedMessagesResult:
    """压缩后的消息结果。"""

    messages: list[ChatMessage]
    compact_tokens: Optional[int] = None


def build_compact_prompt(messages: list[ChatMessage]) -> str:
    """构造压缩提示词。

    输入的是当前完整历史，不再保留 anchor/recent 分段。
    """
    lines = [
        NO_TOOLS_PREAMBLE,
        "",
        BASE_COMPACT_PROMPT,
        "",
        "下面是需要压缩的完整对话历史，格式为逐行 JSON ChatMessage 对象。",
        "第 6 部分必须从这些对象中逐字保留用户消息原文。",
        "",
        "<conversation>",
    ]

    for message in messages:
        lines.append(message.model_dump_json(exclude_none=True))

    lines.extend(
        [
            "</conversation>",
            "",
            "只返回压缩结果。不要包含 [COMPACT_SUMMARY]。",
        ]
    )

    return "\n".join(lines)


def extract_compact_summary(raw_output: str) -> str:
    """从模型输出里取出 <summary> 内容。

    如果模型没有按标签输出，就尽量去掉 analysis 段后返回剩余内容，避免压缩失败。
    """
    text = (raw_output or "").strip()
    summary_match = re.search(r"<summary>([\s\S]*?)</summary>", text, re.IGNORECASE)
    if summary_match:
        return summary_match.group(1).strip()
    return re.sub(
        r"<analysis>[\s\S]*?</analysis>", "", text, flags=re.IGNORECASE
    ).strip()


def build_compact_summary_message(summary_text: str) -> ChatMessage:
    """把摘要文本包装成一条 system 消息。"""

    return ChatMessage(
        role="system",
        content=f"{COMPACT_SUMMARY_PREFIX}\n\n{summary_text.strip()}",
    )


class HistoryCompactor:
    """协调模型适配器，把完整历史消息压缩成新的消息列表。"""

    def __init__(self, adapter: ModelAdapter):
        self.adapter = adapter

    def compact_messages(self, messages: list[ChatMessage]) -> CompactedMessagesResult:
        """把原始消息列表压缩成一条 compact summary system message。"""
        if not messages:
            return CompactedMessagesResult(messages=[])

        compact_prompt = build_compact_prompt(messages)
        request = ModelRequest(
            messages=[
                ChatMessage(role="system", content=compact_prompt),
            ],
            tools=[],
            config=ModelConfig(stream=False),
        )
        summary_response = self.adapter.generate(request)
        summary_text = extract_compact_summary(summary_response.content or "")

        if summary_response.usage and summary_response.usage.input_tokens:
            compact_tokens = summary_response.usage.input_tokens
        else:
            compact_tokens = None

        if not summary_text:
            return CompactedMessagesResult(messages=[], compact_tokens=compact_tokens)

        return CompactedMessagesResult(
            messages=[build_compact_summary_message(summary_text)],
            compact_tokens=compact_tokens,
        )
