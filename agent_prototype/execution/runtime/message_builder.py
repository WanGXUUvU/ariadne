"""应用服务层 (Application Layer) - 大模型请求组装器

职责：
1. 组合 Agent 状态、提示词模板和当前可用工具定义。
2. 组装为符合 API 标准的 ModelRequest 请求实体。

不负责：
1. 网络请求发起和流式输出读取。
2. 系统模板的物理文件磁盘读取。

数据流向：
- 输入：当前 AgentState、AgentDefinition、ToolRegistry 注册表。
- 输出：标准的 ModelRequest 大模型入参结构包。
- 上游来源：agent_prototype/execution/runtime/agent_runtime.py。
- 下游流向：提供给大模型适配层（ModelAdapter）消费。
"""

from typing import Optional

from agent_prototype.agent.definition import AgentDefinition
from agent_prototype.api.dto.schemas import AgentState, ChatMessage
from agent_prototype.model.types.model_types import ModelConfig, ModelRequest
from agent_prototype.tools.registry import ToolRegistry


def build_model_request(
    definition: AgentDefinition,
    state: AgentState,
    tool_registry: ToolRegistry,
    allow_tool_names: Optional[list[str]] = None,
    session_id: str = "",
) -> ModelRequest:
    """这是一个“大模型请求打包盒”。
    它的作用是把大模型需要知道的所有背景设定、历史聊天记录、以及大模型这会儿允许调用的所有工具清单（Schemas），
    全部整整齐齐地装进一个叫 `ModelRequest` 的规范盒子里，然后交给大模型适配器拿去发网络请求。

    需要拿到的东西：
    - definition: 包含系统提示词（人设）的智能体定义配置。
    - state: 包含之前所有多轮历史对话消息的聊天状态。
    - tool_registry: 工具注册中心（工具箱），用于获取具体工具的描述 Schema。
    - allow_tool_names: 这一步大模型被授权使用的工具名字列表（如果是空就从定义里取）。
    - session_id: 会话的唯一 ID（用于追踪调试）。

    会给出来的结果：
    - 一个规范的 ModelRequest 大模型请求实体包，大模型适配器直接认它。
    """

    return ModelRequest(
        messages=[
            ChatMessage(role="system", content=definition.system_prompt),
            *state.messages,
        ],
        tools=tool_registry.get_tool_schemas(allow_tool_names),
        config=ModelConfig(
            model=None,
            stream=False,
        ),
        metadata={"session_id": session_id},
    )
