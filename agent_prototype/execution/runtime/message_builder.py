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
    """把 runtime state 组成一次调用请求。"""

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
