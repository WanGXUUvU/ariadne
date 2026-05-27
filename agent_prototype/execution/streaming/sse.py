"""SSE 工具函数。

封装 Server-Sent Events 协议相关的工具函数：
- _sse_frame    : 将 StreamFrame 序列化为 SSE 协议字符串。
- build_reply_preview : 截断回复文本，生成单行摘要。
"""

from agent_prototype.api.dto.schemas import StreamFrame


def _sse_frame(frame: StreamFrame) -> str:
    """【大白话解释】
    这是一个“SSE 协议数据包装机”。
    它把我们智能体运行中产生的各种事件结构体数据（比如大模型吐字、调用工具、审批请求等），
    序列化为符合浏览器 SSE（Server-Sent Events）标准规范的文本格式（即以 `data: ` 开头并以两个换行符结尾的字符串），
    这样前端网页就能通过 EventSource 正常接收和解析了。

    需要拿到的东西：
    - frame: 待包装的 StreamFrame 数据帧对象。

    会给出来的结果：
    - 符合 SSE 协议要求的规范字符串（以 `\n\n` 结尾）。
    """
    return f"data: {frame.model_dump_json()}\n\n"


def build_reply_preview(reply: str, max_len: int = 120) -> str:
    """【大白话解释】
    这是一个“超简短回答摘要生成器”。
    当智能体洋洋洒洒回答了一大堆字时，如果直接把所有字塞进会话列表里，页面会显得很挤。
    这个生成器就是把完整的多行长文本压缩成一行，并且最多只保留 120 个字（超出的截断），方便做列表预览展示。

    需要拿到的东西：
    - reply: 完整的回答文本。
    - max_len: 最大保留的字数长度（默认 120 个字符）。

    会给出来的结果：
    - 处理后的单行摘要纯文本字符串。
    """
    text = " ".join(reply.split())
    return text[:max_len]
