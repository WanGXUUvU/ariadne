"""执行层类型定义。

职责：定义执行层数据载体。
"""

from dataclasses import dataclass

from agent_prototype.core.types import AgentState
from agent_prototype.core.adapters.chat_completions import ChatCompletionsAdapter
from agent_prototype.security.policy import ApprovalPolicy
from agent_prototype.core.types import AgentDefinition


@dataclass
class RunContext:
    """这是一个用来装"智能体单次运行所需的所有背景物料"的小背包（数据载体）。
    里面装了智能体现在的聊天状态、它的定义设定、与大模型沟通的适配器、审批规则、它的名字、工作区路径、以及会话类型。
    """
    state: AgentState
    definition: AgentDefinition
    adapter: ChatCompletionsAdapter
    approval_policy: ApprovalPolicy
    effective_agent_name: str
    workspace_path: str
    session_type: str
