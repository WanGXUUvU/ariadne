from concurrent.futures import TimeoutError
from agent_prototype.core.tool_types import ToolDefinition,RiskLevel
from agent_prototype.core.schemas import ToolResult, ToolError

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

def build_wait_child_agent_tool(futures: dict) -> ToolDefinition:
    def wait_child_agent(child_run_id: str) -> ToolResult:
        f = futures.get(child_run_id)
        if f is None:
            return ToolResult(
                ok=False,
                error=ToolError(code="not_found", tool_name="wait_child_agent",
                                message=f"child_run_id {child_run_id} not found"),
                metadata={"tool_name": "wait_child_agent"}
            )
        try:
            output = f.result(timeout=120)
            return ToolResult(
                ok=True,
                content=output.reply,
                metadata={"tool_name": "wait_child_agent", "child_run_id": child_run_id}
            )
        except TimeoutError:
            return ToolResult(
                ok=False,
                error=ToolError(code="timeout", tool_name="wait_child_agent",
                                message="timed out after 120s"),
                metadata={"tool_name": "wait_child_agent"}
            )
        except Exception as e:
            return ToolResult(
                ok=False,
                error=ToolError(code="child_error", tool_name="wait_child_agent",
                                message=str(e)),
                metadata={"tool_name": "wait_child_agent"}
            )

    return ToolDefinition(name="wait_child_agent", schema=SCHEMA, handler=wait_child_agent,risk_level=RiskLevel.SAFE)