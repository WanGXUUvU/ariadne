"""
from backend.tools.result_types import ToolResult
from backend.tools.types import RiskLevel
[九层模型 - L3 工具层 (Tools Layer)]

文件职责：
- 非阻塞查询一批异步子智能体运行状态的桥接工具（check_child_status）。
- 接收 `status_checker` 纯闭包回调，消除对底座 Future 对象的直接读取和泄漏。
- 负责校验入参并返回各子任务的 running、done、error、not_found 状态字典。

上游依赖：L8 执行层通过 build_run_registry 进行闭包回调注入。
下游依赖：纯无状态 Callable 接口。
"""

from typing import Callable
from backend.tools.types import ToolDefinition
from backend.tools.result_types import ToolResult
from backend.tools.types import RiskLevel
import json


def build_check_child_status_tool(
    status_checker: Callable[[list[str]], dict],
) -> ToolDefinition:
    """这是一个“子智能体状态查询工具的加工厂（构建函数）”。
    它接收一个用来真正干活的查询回调函数，然后把真正的工具定义（ToolDefinition）给加工并打包出来。

    需要拿到的东西：
    - status_checker (Callable): 一个帮它打听状态的回调函数，只要给出一串子 Agent ID，这个回调就能返回它们现在的最新状态。

    会给出来的结果：
    - ToolDefinition: 最终可以在 AI 面前登记注册的“查询子智能体状态”的工具定义对象。
    """

    def check_child_status(child_run_ids: str) -> ToolResult:
        """这是真正的“查询子智能体状态”的工具执行函数。
        它会去查一查之前派出去干异步任务的“子智能体小帮手们”现在都进行到哪一步了（是还在跑、已经跑完、出错了、还是根本找不到这个小帮手）。它不会傻等小帮手干完，而是“非阻塞”地看一眼状态就走。

        需要拿到的东西：
        - child_run_ids (str): 一串需要查询的子任务 ID 列表，需要是 JSON 数组格式（例如：`'["id1", "id2"]'`）。

        会给出来的结果：
        - ToolResult: 一个包含查询结果的数据包。如果成功，里面的 content 就是各个 ID 的状态（比如running、done、error）；如果解析失败或出错，ok 就会是 False。
        """
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
                        "description": '要查询的子 Agent ID 列表，JSON 数组格式，如 ["id1", "id2"]',
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
