"""
from agent_prototype.tools.result_types import ToolResult, ToolError
from agent_prototype.tools.types import RiskLevel
[九层模型 - L3 工具层 (Tools Layer)]

文件职责：
- 阻塞等待指定子智能体运行结束并拉取其最终 reply 文本的桥接工具（wait_child_agent）。
- 接收 `child_waiter` 纯闭包回调，消除对 Future 超时等待逻辑的直接调用。
- 捕获并处理 LookupError (未找到)、TimeoutError (超时)、以及各种内部运行时异常并包装为规范 of ToolResult。

上游依赖：L8 执行层通过 build_run_registry 进行闭包回调注入。
下游依赖：纯无状态 Callable 接口。
"""

from concurrent.futures import TimeoutError
from typing import Callable
from agent_prototype.tools.types import ToolDefinition
from agent_prototype.tools.result_types import ToolResult, ToolError
from agent_prototype.tools.types import RiskLevel


def build_wait_child_agent_tool(child_waiter: Callable[[str], str]) -> ToolDefinition:
    """这是一个“等待子智能体工具的加工厂（构建函数）”。
    它接收一个用来阻塞等待的回调函数，然后将“等待子智能体小帮手并拿回结果”这个工具的定义（ToolDefinition）给加工并打包出来。

    需要拿到的东西：
    - child_waiter (Callable): 一个用于阻塞等待并拉取子智能体回复内容的回调函数。

    会给出来的结果：
    - ToolDefinition: 加工好、随时能提供给 AI 使用的“等待子智能体”工具定义对象。
    """

    def wait_child_agent(child_run_id: str) -> ToolResult:
        """这是真正的“等待子智能体小帮手完成工作”的工具执行函数。
        当你通过 spawn 派出了小助手，但是又急需它的成果时，你可以调用这个函数。它会耐心在原地阻塞等待（最长等待 120 秒），一旦小帮手干完了，就立刻把它的最终回复文本拉回来给你。如果等了很久都超时了，或者根本找不到这个 ID，它会返回相应的报错信息。

        需要拿到的东西：
        - child_run_id (str): 之前派发任务时拿到的唯一任务凭证 ID。

        会给出来的结果：
        - ToolResult: 一个包含执行结果的数据包。如果等到了，content 就是子智能体小助手的最终答复文本；如果超时或出错，ok 会是 False 并且带有错误详情。
        """
        try:
            reply = child_waiter(child_run_id)
            return ToolResult(
                ok=True,
                content=reply,
                metadata={"tool_name": "wait_child_agent", "child_run_id": child_run_id},
            )
        except LookupError as e:  # 当 ID 未找到时抛出 LookupError
            return ToolResult(
                ok=False,
                error=ToolError(code="not_found", tool_name="wait_child_agent", message=str(e)),
                metadata={"tool_name": "wait_child_agent"},
            )
        except TimeoutError:
            return ToolResult(
                ok=False,
                error=ToolError(
                    code="timeout", tool_name="wait_child_agent", message="timed out after 120s"
                ),
                metadata={"tool_name": "wait_child_agent"},
            )
        except Exception as e:
            return ToolResult(
                ok=False,
                error=ToolError(code="child_error", tool_name="wait_child_agent", message=str(e)),
                metadata={"tool_name": "wait_child_agent"},
            )

    SCHEMA = {
        "type": "function",
        "function": {
            "name": "wait_child_agent",
            "description": (
                "阻塞等待指定子 Agent 完成，直接返回其最终回复文本。"
                "最多等待 120 秒，超时返回 timeout 错误。"
                "【重要】调用 spawn_child_agent 后，必须在同一轮内紧接着调用本工具等待结果，不要等用户再次询问。"
                "如需同时等待多个子任务，对每个 child_run_id 依次调用本工具。"
                "若已通过 check_child_status 确认状态为 done，也可直接从 check 结果的 reply 字段取值，无需再调用本工具。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "child_run_id": {
                        "type": "string",
                        "description": "spawn_child_agent 返回的 child_run_id",
                    }
                },
                "required": ["child_run_id"],
                "additionalProperties": False,
            },
        },
    }

    return ToolDefinition(
        name="wait_child_agent", schema=SCHEMA, handler=wait_child_agent, risk_level=RiskLevel.SAFE
    )
