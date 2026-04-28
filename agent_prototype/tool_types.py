from dataclasses import dataclass  # 定义不可变工具对象
from typing import Callable

@dataclass(frozen=True)  # 工具定义不可变，避免运行中被改坏
class ToolDefinition:  # 单个工具的描述
    name: str  # 工具名
    schema: dict  # 给模型看的 schema
    handler: Callable[..., str]  # 真正执行工具的函数
