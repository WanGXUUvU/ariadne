"""应用服务层 (Application Layer) - 大模型请求组装器

职责：
1. 组合 Agent 状态、提示词模板和当前可用工具定义。
2. 组装为符合 API 标准的 ModelRequest 请求实体。

不负责：
1. 网络请求发起和流式输出读取。
2. 系统模板的物理文件磁盘读取。

数据流向：
- 输入：当前 RunState、AgentDefinition、ToolRegistry 注册表。
- 输出：标准的 ModelRequest 大模型入参结构包。
- 上游来源：backend/execution/runtime/agent_runner.py。
- 下游流向：提供给大模型适配层（ModelAdapter）消费。
"""

from backend.agent.types import AgentDefinition
from backend.core.types import ChatMessage, ModelConfig, ModelRequest
from backend.execution.runtime.types import RunState
from backend.tools.registry import ToolRegistry


def build_model_request(
    agent_profile: AgentDefinition,
    state: RunState,
    tool_registry: ToolRegistry,
) -> ModelRequest:
    """打包系统提示词 + 历史消息 + 可用工具清单 -> ModelRequest。"""

    return ModelRequest(
        messages=[
            ChatMessage(role="system", content=agent_profile.system_prompt),
            *state.messages,
        ],
        tools=tool_registry.get_tool_schemas(agent_profile.tool_names),
        config=ModelConfig(
            model=None,
            stream=False,
        ),
    )
