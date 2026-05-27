"""
[九层模型 - L3 工具层 (Tools Layer)]

文件职责：
- 异步派发子智能体任务的桥接工具（spawn_child_agent）。
- 接收 `child_dispatcher` 纯闭包回调，彻底与 L8 认知引擎和 L5 物理落库解耦，排除一切物理 import。
- 仅负责接收模型意图，调用回调获取 child_run_id，并包装为 ToolResult 返回给上层。

上游依赖：L8 执行层通过 build_run_registry 进行闭包回调注入。
下游依赖：纯无状态 Callable 接口。
"""
from typing import Callable
from agent_prototype.tools.protocol import ToolDefinition, RiskLevel
from agent_prototype.model.types.domain import ToolResult

def build_spawn_child_agent_tool(child_dispatcher: Callable[[str, str], str]) -> ToolDefinition:
    """这是一个“派发（召唤）子智能体工具的加工厂（构建函数）”。
    它接收一个用来真正分发任务的回调函数，然后将“召唤子智能体小帮手”这个工具的定义（ToolDefinition）给加工并打包出来。

    需要拿到的东西：
    - child_dispatcher (Callable): 一个用于真正派发子智能体任务的回调函数。

    会给出来的结果：
    - ToolDefinition: 加工好、随时能提供给 AI 使用的“召唤子智能体”工具定义对象。
    """

    def spawn_child_agent(task: str, agent_name: str = "子Agent") -> ToolResult:
        """这是真正的“召唤子智能体去干活”的工具执行函数。
        它可以在后台叫出一个专属的“子 Agent 小帮手”，把任务分给它去异步执行。这个函数会非常爽快，叫完人、发完任务，立马塞给你一个唯一的任务凭证（child_run_id），根本不用等小帮手做完就结束了。

        需要拿到的东西：
        - task (str): 派发给子智能体的具体任务描述（比如：“请帮我把这个文件夹下的 Python 文件都检查一遍”）。
        - agent_name (str, 默认 "子Agent"): 给你派出的这个小助手起个好听的职称（比如：“代码审查员”），方便在界面上好看。

        会给出来的结果：
        - ToolResult: 一个包含任务凭证（child_run_id）的结果对象。如果派发成功，可以通过 `content` 拿到这个 ID；如果派发出错，ok 会是 False。
        """
        try:
            child_run_id = child_dispatcher(task, agent_name)
            return ToolResult(
                ok=True,
                content=child_run_id,
                metadata={"tool_name": "spawn_child_agent", "child_run_id": child_run_id, "agent_name": agent_name},
            )
        except Exception as e:
            return ToolResult(
                ok=False,
                content=f"Failed to spawn child agent: {e}",
                metadata={"tool_name": "spawn_child_agent", "agent_name": agent_name},
            )
    
    SCHEMA = {
        "type": "function",
        "function": {
            "name": "spawn_child_agent",
            "description": (
                "把一个独立子任务委派给子 Agent 异步执行。"
                "立即返回 child_run_id 字符串，不等待任务完成。"
                "【单任务模式】派出后立即调用 wait_child_agent(child_run_id) 阻塞等待结果，再回复用户。不要先对用户说'正在等待'就停下。"
                "【并行模式】需要同时派发多个子任务时，先连续调用多次 spawn_child_agent，"
                "然后用 check_child_status 逐一查询各子任务状态：若已 done 则直接从 reply 字段取值；"
                "若仍 running 则对该 child_run_id 单独调用 wait_child_agent 阻塞等待其完成再取结果。"
                "全部子任务结果收齐后，汇总回复用户。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "子 Agent 需要完成的具体任务描述",
                    },
                    "agent_name": {
                        "type": "string",
                        "description": "子 Agent 的角色名称，用于前端展示，如'数据分析师'、'代码审查员'。不填默认为'子Agent'。",
                    },
                },
                "required": ["task"],
                "additionalProperties": False,
            },
        },
    }

    return ToolDefinition(
        name="spawn_child_agent",
        schema=SCHEMA,
        handler=spawn_child_agent,
        risk_level=RiskLevel.SAFE,
    )