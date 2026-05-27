"""SSE 工具函数。

封装 Server-Sent Events 协议相关的工具函数：
- _sse_frame    : 将 StreamFrame 序列化为 SSE 协议字符串。
- build_reply_preview : 截断回复文本，生成单行摘要。
"""

from agent_prototype.api.dto.schemas import StreamFrame


def _sse_frame(frame: StreamFrame) -> str:
    """将 StreamFrame 序列化为 SSE 协议格式字符串。"""
    return f"data: {frame.model_dump_json()}\n\n"


def build_reply_preview(reply: str, max_len: int = 120) -> str:
    """将完整回复文本压缩为单行预览摘要。"""
    text = " ".join(reply.split())
    return text[:max_len]
