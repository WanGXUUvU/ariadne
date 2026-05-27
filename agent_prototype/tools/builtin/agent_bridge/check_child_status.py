"""
[九层模型 - L3 工具层 (Tools Layer)]

文件职责：
- 非阻塞查询一批异步子智能体运行状态的桥接工具（check_child_status）。
- 接收 `status_checker` 纯闭包回调，消除对底座 Future 对象的直接读取和泄漏。
- 负责校验入参并返回各子任务的 running、done、error、not_found 状态字典。

上游依赖：L8 执行层通过 build_run_registry 进行闭包回调注入。
下游依赖：纯无状态 Callable 接口。
"""
from typing import Callable
from agent_prototype.tools.protocol import ToolDefinition
from agent_prototype.model.types.domain import ToolResult, RiskLevel
import json

def build_check_child_status_tool(status_checker: Callable[[list[str]], dict]) -> ToolDefinition:

    def check_child_status(child_run_ids: str) -> ToolResult:
        try:
            ids = json.loads(child_run_ids)  # "[\"aaa\",\"bbb\"]" → ["aaa", "bbb"]
        except json.JSONDecodeError as exc:
            return ToolResult(ok=False, content=f"Invalid JSON: {exc}")
        
        try:
            result = status_checker(ids)
            return ToolResult(ok=True, content=json.dumps(result, ensure_ascii=False))
        except Exception as e:
            return ToolResult(ok=False, content=f"Failed to check status: {e}")

    SCHEMA = {
        "type": "function",
        "function": {
            "name": "check_child_status",
            "description": (
                "非阻塞查询一批子 Agent 的运行状态。"
                "返回每个 child_run_id 对应的状态：running（仍在执行）、done（已完成，reply 字段含最终回复）、error（失败，error 字段含原因）、not_found（id 不存在）。"
                "适合并行场景：先 spawn 多个子任务，再用此工具轮询，处理已完成的同时等待未完成的。"
                "当所有任务均为 done 时，从各条目的 reply 字段提取结果即可，无需再调用 wait_child_agent。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "child_run_ids": {
                        "type": "string",
                        "description": "要查询的子 Agent ID 列表，JSON 数组格式，如 [\"id1\", \"id2\"]",
                    },
                },
                "required": ["child_run_ids"],
                "additionalProperties": False,
            },
        },
    }

    return ToolDefinition(
        name="check_child_status",
        schema=SCHEMA,
        handler=check_child_status,
        risk_level=RiskLevel.SAFE,
    )