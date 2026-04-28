import json  # 解析工具参数 JSON
from typing import  Optional  # 类型标注

from .tool_types import ToolDefinition
from .tools_defs.echo import build_echo_tool_definition
from .tools_defs.fs_read import build_read_file_tool_definition
from .tools_defs.fs_list import build_list_dir_definition
from .tools_defs.fs_write import build_write_file_tool_definition
from .tools_defs.fs_search import build_search_text_definition


class ToolRegistry:  # 工具注册中心
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}  # 用名字保存所有工具
    #注册时会把完整的ToolDefiniton注册进去
    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool  # 注册工具
    #把注册的tool的schema 抽出来 组成一个列表
    def get_tool_schemas(self, tool_names: Optional[list[str]] = None) -> list[dict]:
        if tool_names is None:
            tools = self._tools.values()  # 返回全部工具
        else:
            tools = [self._tools[name] for name in tool_names if name in self._tools]  # 只取存在的工具

        return [tool.schema for tool in tools]  # 只返回 schema 列表

    def execute_tool_call(self, name: str, arguments: str) -> str:
        tool = self._tools.get(name)  # 按名字找工具
        if tool is None:
            raise ValueError(f"Unknown tool: {name}")  # 明确报错

        args = json.loads(arguments or "{}")  # 解析 JSON 参数
        return tool.handler(**args)  # 调用实际 handler


def build_default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()  # 创建默认 registry

    registry.register(build_read_file_tool_definition())
    registry.register(build_echo_tool_definition())
    registry.register(build_list_dir_definition())
    registry.register(build_write_file_tool_definition())
    registry.register(build_search_text_definition())

    return registry


DEFAULT_TOOL_REGISTRY = build_default_tool_registry()  # 默认注册中心
