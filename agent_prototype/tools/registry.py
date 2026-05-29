"""
[九层模型 - L3 工具注册中心 (Tool Registry Layer)]

文件职责：
- 管理所有可用工具（ToolDefinition）的加载、克隆与映射。
- 封装工具参数 JSON 解析、安全校验、类型错误防范、以及统一的运行时工具执行。
- 接收 `child_dispatcher`、`status_checker`、`child_waiter` 回调并组装出包含桥接工具的 ToolRegistry。

上游依赖：L8 执行层 (RunService)。
下游依赖：L3 各项内置工具文件定义。
"""

import json  # 解析工具参数 JSON
from typing import Optional, Callable  # 类型标注

from agent_prototype.tools.types import RiskLevel
from agent_prototype.tools.types import ToolDefinition
from agent_prototype.tools.result_types import ToolError, ToolResult
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
    """工具注册管理中心类 (OOP)

    这个类是一个“工具百宝箱/工具柜”。
    用来统一保管系统里所有大大小小的工具（比如读文件、写文件、网络搜索、召唤子智能体等）。它不仅负责把新工具贴好标签收纳起来（register），还能把工具的说明书拿给 AI 看（get_tool_schemas），以及当 AI 决定调用某个工具时，负责把参数解析好，启动真正的工具代码并安全地把执行结果拿回来（execute_tool_call）。
    """

    def __init__(self) -> None:
        """工具百宝箱初始化，准备好一个空的收纳架。"""
        self._tools: dict[str, ToolDefinition] = {}  # 用名字保存所有工具

    def clone(self) -> "ToolRegistry":
        """把当前的百宝箱完整复制一份新的（深拷贝收纳架上的工具索引），以防在不同的会话或运行轨迹里互相干扰。

        会给出来的结果：
        - ToolRegistry: 一个跟当前一模一样但互相独立的新百宝箱实例。
        """
        new = ToolRegistry()
        new._tools = dict(self._tools)
        return new

    # 注册时会把完整的 ToolDefinition 注册进去
    def register(self, tool: ToolDefinition) -> None:
        """往百宝箱里登记并收纳一个新工具。

        需要拿到的东西：
        - tool (ToolDefinition): 编写好并打包规范的工具定义对象。
        """
        self._tools[tool.name] = tool  # 注册工具

    # 把注册的 tool 的 schema 抽出来 组成一个列表
    def get_tool_schemas(self, tool_names: Optional[list[str]] = None) -> list[dict]:
        """抽调出工具的“使用说明书”（JSON Schema 描述）汇集成一个列表，好打包塞给 AI，让 AI 知道有哪些工具可以点、每个工具该怎么喂参数。

        需要拿到的东西：
        - tool_names (list[str], 可选): 想要提取说明书的工具名称列表。如果不传，默认把百宝箱里全部工具的说明书都拿出来。

        会给出来的结果：
        - list[dict]: 所有被选中的工具的说明书字典列表。
        """
        if tool_names is None:
            tools = self._tools.values()  # 返回全部工具
        else:
            tools = [
                self._tools[name] for name in tool_names if name in self._tools
            ]  # 只取存在的工具

        return [tool.schema for tool in tools]  # 只返回 schema 列表

    def get_risk_level(self, name: str) -> RiskLevel:
        """查看某个工具的安全风险等级（是纯人畜无害的 SAFE，还是需要申请审批的写磁盘 WRITE/敏感操作等）。

        需要拿到的东西：
        - name (str): 工具的名字。

        会给出来的结果：
        - RiskLevel: 该工具的风险等级。若工具没找到，默认为最安全的 SAFE。
        """
        tool = self._tools.get(name)
        if tool is None:
            return RiskLevel.SAFE
        return tool.risk_level

    def execute_tool_call(self, name: str, arguments: str) -> ToolResult:
        """当 AI 决定要用某个工具时，由这个函数来“拉开架势，安全执行”。
        它会先从百宝箱里找到这个工具，然后把 AI 吐出来的一大串 JSON 参数字符串解析成 Python 字典，最后小心翼翼地调用工具底层的 Python 函数。中途如果参数解析失败、或者工具执行报错，它会把错误包装得工工整整地返回，而不是直接让整个系统崩溃。

         need拿到的东西：
        - name (str): 要执行的工具名称。
        - arguments (str): AI 传给工具的 JSON 参数字符串。

        会给出来的结果：
        - ToolResult: 包含执行是否成功、以及工具吐出来的最终成果（或报错详情）的统一结果对象。
        """
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
                    code="invalid_arguments", tool_name=name, message="Invalid JSON arguments"
                ),
                metadata={"tool_name": name, "raw_arguments": arguments, "debug": str(exc)},
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

        if isinstance(result, ToolResult):  # 如果 handler 已经返回 ToolResult
            return result

        return ToolResult(
            ok=True,
            content=str(result),
            metadata={"tool_name": name},
        )


def build_default_tool_registry() -> ToolRegistry:
    """创建一个默认的百宝箱，并预先塞入所有最常用、最基础的内置工具（比如读写文件、回声测试、网络搜索等）。

    会给出来的结果：
    - ToolRegistry: 装载了默认工具集的百宝箱。
    """
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
    """为单次会话执行构建一个专属的百宝箱。
    不仅包含默认的所有内置工具，还会把跟“召唤和等待子智能体小帮手”相关的专属桥接工具（配好了相关的异步回调函数）也一起塞进百宝箱。

    需要拿到的东西：
    - child_dispatcher (Callable): 派发子智能体任务的回调。
    - status_checker (Callable): 查询子智能体状态的回调。
    - child_waiter (Callable): 阻塞等待子智能体结果的回调。

    会给出来的结果：
    - ToolRegistry: 装载了所有普通工具和专属小助手调度桥接工具的完整版百宝箱。
    """
    registry = DEFAULT_TOOL_REGISTRY.clone()
    registry.register(build_spawn_child_agent_tool(child_dispatcher))
    registry.register(build_check_child_status_tool(status_checker))
    registry.register(build_wait_child_agent_tool(child_waiter))
    return registry


DEFAULT_TOOL_REGISTRY = build_default_tool_registry()  # 默认注册中心
