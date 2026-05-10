from typing import Optional

from ..core.agent_definition import AgentDefinition
from ..core.schemas import AgentState, ChatMessage
from ..model.model_types import ModelConfig, ModelRequest
from ..tools.tool_registry import ToolRegistry


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
