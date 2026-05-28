"""上下文层类型定义。

职责：定义上下文装配层的数据载体。
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AssembledContext:
    """这是一个用来装"拼装好的上下文数据"的简单小篮子（数据载体）。
    把拼好的系统提示词和工作区路径打包放在这里，方便后面其他人拿去用。
    """
    system_prompt: str
    workspace_path: Optional[str]
