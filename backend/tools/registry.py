"""工具加载与注册管理中心。

职责：
- 集中管理所有可用工具静态定义（ToolDefinition）的注册与克隆。
- 提供面向大语言模型的工具 JSON Schema（使用说明书）提取方法。
- 提供统一的安全参数解析、运行时隔离执行及异常截获保障。
- 绑定多智能体子任务的异步调度/等待回调函数。

上游：
- RunService
- AgentRunner

下游：
- 各内置工具的 build 函数
- AgentBridge 工具组

不负责：
- 不做具体安全策略的评估与拦截拦截（由安全中间件负责）。
- 不持久化工具调用 Trace（由 ToolTracer 负责）。
"""
import json  # 解析工具参数 JSON
from typing import Optional, Callable, Any  # 类型标注

from backend.mcp.bridge import build_mcp_tool_definitions
from backend.mcp.mcp_manager import get_mcp_server_manager
from backend.tools.types import RiskLevel
from backend.tools.types import ToolDefinition
from backend.tools.result_types import ToolError, ToolResult
from .builtin.util.echo import build_echo_tool_definition
from .builtin.filesystem.fs_read import build_read_file_tool_definition
from .builtin.filesystem.fs_list import build_list_dir_definition
from .builtin.filesystem.fs_write import build_write_file_tool_definition
from .builtin.filesystem.fs_search import build_search_text_definition
from .builtin.search.web_search import build_web_search_tool_definition
from .builtin.agent_bridge.check_child_status import build_check_child_status_tool
from .builtin.agent_bridge.spawn_child_agent import build_spawn_child_agent_tool
from .builtin.agent_bridge.wait_child_agent import build_wait_child_agent_tool


class ToolRegistry:  # 工具注册中心
    """工具注册中心，提供工具发现、Schema 组装与安全调用的注册表容器。"""

    def __init__(self) -> None:
        """初始化空的工具映射字典。"""
        self._tools: dict[str, ToolDefinition] = {}  # 用名字保存所有工具

    def clone(self) -> "ToolRegistry":
        """深拷贝当前工具注册表的只读映射，避免不同运行轨迹互相干扰。"""
        new = ToolRegistry()
        new._tools = dict(self._tools)
        return new

    # 注册时会把完整的 ToolDefinition 注册进去
    def register(self, tool: ToolDefinition) -> None:
        """注册并加载一个工具定义。"""
        self._tools[tool.name] = tool  # 注册工具

    # 把注册的 tool 的 schema 抽出来 组成一个列表
    def get_tool_schemas(self, tool_names: Optional[list[str]] = None) -> list[dict]:
        """提取指定或全部工具的 JSON Schema（模型侧描述契约）列表。"""
        if tool_names is None:
            tools = self._tools.values()  # 返回全部工具
        else:
            tools = [
                self._tools[name] for name in tool_names if name in self._tools
            ]  # 只取存在的工具

        return [tool.schema for tool in tools]  # 只返回 schema 列表

    def get_risk_level(self, name: str) -> RiskLevel:
        """获取指定工具的安全风险等级，默认返回 SAFE。"""
        tool = self._tools.get(name)
        if tool is None:
            return RiskLevel.SAFE
        return tool.risk_level

    def execute_tool_call(
        self, name: str, arguments: str, context: Optional[Any] = None
    ) -> ToolResult:
        """安全解析入参并执行指定工具，拦截底层一切异常并包装为统一的 ToolResult。"""
        # 强制从 context 中提取 workspace_path 进行安全和投影改写
        workspace_path = getattr(context, "workspace_path", None)

        if workspace_path:
            from backend.security.sandbox.resolver import SandboxPathResolver

            ok, modified_args, err_msg = SandboxPathResolver.resolve_and_rewrite(
                name, arguments, workspace_path
            )
            if not ok:
                return ToolResult(
                    ok=False,
                    error=ToolError(
                        code="SANDBOX_VIOLATION",
                        tool_name=name,
                        message=err_msg or "Sandbox Violation",
                    ),
                    metadata={"tool_name": name},
                )
            arguments = modified_args

        tool = self._tools.get(name)  # 按名字找工具
        if tool is None:
            return ToolResult(
                ok=False,
                error=ToolError(
                    code="unknown_tool",  # 错误码
                    tool_name=name,  # 工具名
                    message=f"Unknown tool: {name}",  # 错误信息
                ),
                metadata={"tool_name": name},
            )

        try:
            args = json.loads(arguments or "{}")  # 字符串变成字典
        except json.JSONDecodeError as exc:  # 参数不是合法 json
            return ToolResult(
                ok=False,
                error=ToolError(
                    code="invalid_arguments",
                    tool_name=name,
                    message="Invalid JSON arguments",
                ),
                metadata={
                    "tool_name": name,
                    "raw_arguments": arguments,
                    "debug": str(exc),
                },
            )
        try:  # 尝试执行工具
            import inspect

            sig = inspect.signature(tool.handler)
            if "__context__" in sig.parameters:
                args["__context__"] = context
            result = tool.handler(**args)  # 调用 handler
        except TypeError as exc:
            return ToolResult(
                ok=False,
                error=ToolError(
                    code="invalid_arguments", tool_name=name, message=str(exc)
                ),
                metadata={"tool_name": name},
            )
        except Exception as exc:
            return ToolResult(
                ok=False,
                error=ToolError(
                    code="tool_runtime_error", tool_name=name, message=str(exc)
                ),
                metadata={"tool_name": name},
            )

        if not isinstance(result, ToolResult):
            return ToolResult(
                ok=False,
                error=ToolError(
                    code="invalid_tool_result",
                    tool_name=name,
                    message=f"Tool {name} must return ToolResult",
                ),
                metadata={"tool_name": name},
            )

        return result


def build_default_tool_registry() -> ToolRegistry:
    """构建并初始化包含全部基础内置工具的全局默认注册表。"""
    registry = ToolRegistry()  # 创建默认 registry

    registry.register(build_read_file_tool_definition())
    registry.register(build_echo_tool_definition())
    registry.register(build_list_dir_definition())
    registry.register(build_write_file_tool_definition())
    registry.register(build_search_text_definition())
    registry.register(build_web_search_tool_definition())
    return registry


def build_run_registry(
    child_dispatcher: Callable[[str, str], str],
    status_checker: Callable[[list[str]], dict],
    child_waiter: Callable[[str], str],
) -> ToolRegistry:
    registry = DEFAULT_TOOL_REGISTRY.clone()

    mcp_server_manager = get_mcp_server_manager()
    try:
        discovered_mcp_tools = mcp_server_manager.list_all_tools()
    except RuntimeError as exc:
        print(f"[MCP] skip tool registration: {exc}")
        discovered_mcp_tools = []

    mcp_tool_definitions = build_mcp_tool_definitions(discovered_mcp_tools)
    for tool in mcp_tool_definitions:
        registry.register(tool)

    registry.register(build_spawn_child_agent_tool(child_dispatcher))
    registry.register(build_check_child_status_tool(status_checker))
    registry.register(build_wait_child_agent_tool(child_waiter))
    return registry


DEFAULT_TOOL_REGISTRY = build_default_tool_registry()  # 默认注册中心
