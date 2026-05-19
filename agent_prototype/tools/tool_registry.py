import json  # 解析工具参数 JSON
from typing import  Optional  # 类型标注

from ..core.schemas import ToolError, ToolResult
from ..core.tool_types import ToolDefinition,RiskLevel
from .builtin.echo import build_echo_tool_definition
from .builtin.fs_read import build_read_file_tool_definition
from .builtin.fs_list import build_list_dir_definition
from .builtin.fs_write import build_write_file_tool_definition
from .builtin.fs_search import build_search_text_definition
from .builtin.web_search import build_web_search_tool_definition
from .builtin.check_child_status import build_check_child_status_tool
from .builtin.wait_child_agent import build_wait_child_agent_tool


class ToolRegistry:  # 工具注册中心
    def __init__(self) -> None:
        """输入：无。输出：初始化后的 ToolRegistry 实例。"""
        self._tools: dict[str, ToolDefinition] = {}  # 用名字保存所有工具

    def clone(self)->"ToolRegistry":
        
        new = ToolRegistry()
        new._tools=dict(self._tools)
        return new
    
    #注册时会把完整的ToolDefiniton注册进去
    def register(self, tool: ToolDefinition) -> None:
        """输入：一个 ToolDefinition。输出：无，副作用是把工具注册进内存字典。"""
        self._tools[tool.name] = tool  # 注册工具
    #把注册的tool的schema 抽出来 组成一个列表
    def get_tool_schemas(self, tool_names: Optional[list[str]] = None) -> list[dict]:
        """输入：可选的工具名列表。输出：给模型使用的工具 schema 列表。"""
        if tool_names is None:
            tools = self._tools.values()  # 返回全部工具
        else:
            tools = [self._tools[name] for name in tool_names if name in self._tools]  # 只取存在的工具

        return [tool.schema for tool in tools]  # 只返回 schema 列表

    def get_risk_level(self,name:str)->RiskLevel:
        tool=self._tools.get(name)
        if tool is None:
            return RiskLevel.SAFE
        return tool.risk_level
    def execute_tool_call(self, name: str, arguments: str) -> ToolResult:
        """输入：工具名、JSON 字符串参数。输出：统一的 ToolResult。"""
        tool = self._tools.get(name)  # 按名字找工具
        if tool is None:
            return ToolResult(
                ok=False,
                error=ToolError(
                    code="unknown_tool",  # 错误码
                    tool_name=name,  # 工具名
                    message=f"Unknown tool: {name}",  # 错误信息
                ),
                metadata={"tool_name":name},
            )

        try:
            args = json.loads(arguments or "{}")  # 字符串变成字典
        except json.JSONDecodeError as exc:#参数不是合法json
            return ToolResult(
                ok=False,
                error=ToolError(code="invalid_arguments", tool_name=name, message="Invalid JSON arguments"),
                metadata={"tool_name":name,"raw_arguments":arguments,"debug":str(exc)},
            )
        try:  # 尝试执行工具
            result = tool.handler(**args)  # 调用 handler
        except TypeError as exc:
            return ToolResult(
                ok=False,
                error=ToolError(code="invalid_arguments", tool_name=name, message=str(exc)),
                metadata={"tool_name": name},
            )
        except Exception as exc:
            return ToolResult(
                ok=False,
                error=ToolError(code="tool_runtime_error", tool_name=name, message=str(exc)),
                metadata={"tool_name": name},
            )
        
        if isinstance(result,ToolResult):# 如果 handler 已经返回 ToolResult
            return result
        
        return ToolResult(
            ok=True,
            content=str(result),
            metadata={"tool_name":name},
        )

def build_default_tool_registry() -> ToolRegistry:
    """输入：无。输出：预注册默认工具后的 ToolRegistry。"""
    registry = ToolRegistry()  # 创建默认 registry

    registry.register(build_read_file_tool_definition())
    registry.register(build_echo_tool_definition())
    registry.register(build_list_dir_definition())
    registry.register(build_write_file_tool_definition())
    registry.register(build_search_text_definition())
    registry.register(build_web_search_tool_definition())
    return registry

def build_run_registry(parent_run_id:str, session_id:str, executor, futures:dict) -> ToolRegistry:
    from .builtin.spawn_child_agent import build_spawn_child_agent_tool
    registry = DEFAULT_TOOL_REGISTRY.clone()
    registry.register(build_spawn_child_agent_tool(parent_run_id, session_id, executor, futures))
    registry.register(build_check_child_status_tool(futures))
    registry.register(build_wait_child_agent_tool(futures))
    return registry

DEFAULT_TOOL_REGISTRY = build_default_tool_registry()  # 默认注册中心
