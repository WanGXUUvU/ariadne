"""SSE 工具函数。

封装 Server-Sent Events 协议相关的工具函数：
- _sse_frame    : 将 StreamFrame 序列化为 SSE 协议字符串。
- build_reply_preview : 截断回复文本，生成单行摘要。
"""

from backend.execution.streaming.types import StreamFrame


def _sse_frame(frame: StreamFrame) -> str:
    """这是一个“SSE 协议数据包装机”。
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
    """生成用于会话列表的单行回复预览。

    将多行/多空格文本合并为单行，并截断到 `max_len` 字符。

    注意：数据库中 `session_records.last_reply_preview` 定义为 `String(120)`，
    因此默认长度设为 120 以保持一致性。
    """
    text = " ".join(reply.split())
    return text[:max_len]
