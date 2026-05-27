"""
[九层模型 - L3 工具层 (Tools Layer)]

文件职责：
- 阻塞等待指定子智能体运行结束并拉取其最终 reply 文本的桥接工具（wait_child_agent）。
- 接收 `child_waiter` 纯闭包回调，消除对 Future 超时等待逻辑的直接调用。
- 捕获并处理 LookupError (未找到)、TimeoutError (超时)、以及各种内部运行时异常并包装为规范的 ToolResult。

上游依赖：L8 执行层通过 build_run_registry 进行闭包回调注入。
下游依赖：纯无状态 Callable 接口。
"""
from concurrent.futures import TimeoutError
from typing import Callable
from agent_prototype.tools.protocol import ToolDefinition, RiskLevel
from agent_prototype.model.types.domain import ToolResult, ToolError

def build_wait_child_agent_tool(child_waiter: Callable[[str], str]) -> ToolDefinition:
    
    def wait_child_agent(child_run_id: str) -> ToolResult:
        try:
            reply = child_waiter(child_run_id)
            return ToolResult(
                ok=True,
                content=reply,
                metadata={"tool_name": "wait_child_agent", "child_run_id": child_run_id}
            )
        except LookupError as e:  # 当 ID 未找到时抛出 LookupError
            return ToolResult(
                ok=False,
                error=ToolError(code="not_found", tool_name="wait_child_agent", message=str(e)),
                metadata={"tool_name": "wait_child_agent"}
            )
        except TimeoutError:
            return ToolResult(
                ok=False,
                error=ToolError(code="timeout", tool_name="wait_child_agent", message="timed out after 120s"),
                metadata={"tool_name": "wait_child_agent"}
            )
        except Exception as e:
            return ToolResult(
                ok=False,
                error=ToolError(code="child_error", tool_name="wait_child_agent", message=str(e)),
                metadata={"tool_name": "wait_child_agent"}
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
                        "description": "spawn_child_agent 返回的 child_run_id"
                    }
                },
                "required": ["child_run_id"],
                "additionalProperties": False,
            }
        }
    }

    return ToolDefinition(
        name="wait_child_agent",
        schema=SCHEMA,
        handler=wait_child_agent,
        risk_level=RiskLevel.SAFE
    )