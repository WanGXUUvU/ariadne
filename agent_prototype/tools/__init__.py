"""工具模块。

统一导出工具层核心类型与服务，使得调用方可以：
    from agent_prototype.tools import ToolDefinition, ToolRegistry
"""

from agent_prototype.tools.types import ToolDefinition
from agent_prototype.tools.registry import (
    ToolRegistry,
    build_default_tool_registry,
    build_run_registry,
    DEFAULT_TOOL_REGISTRY,
)

__all__ = [
    "ToolDefinition",
    "ToolRegistry",
    "build_default_tool_registry",
    "build_run_registry",
    "DEFAULT_TOOL_REGISTRY",
]
