"""安全层类型定义。

职责：定义安全中间件管道所需的上下文数据载体。
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolCallContext:
    """工具调用上下文对象
    
    这是一个"安检小推车（工具调用上下文）"。
    当 AI 想要调一个工具时，它会把这个工具的名字（tool_name）、想传的参数（tool_args）、这次调用的身份证号（tool_call_id）、属于哪个聊天会话（session_id）、以及这次运行的 ID（run_id）通通装在这辆小推车里。小推车还会拉上一个"百宝袋（extra）"，方便安检管道中的各个关卡（中间件）往里塞一些临时的共享小标签。
    """

    tool_name: str
    tool_args: str
    tool_call_id: str
    session_id: str
    run_id: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)
    """元数据字典，用于不同拦截器之间传递自定义状态或配置"""
