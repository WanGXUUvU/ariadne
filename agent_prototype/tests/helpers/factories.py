"""测试假对象工厂。"""

from typing import List, Optional

from agent_prototype.core.types import ChatMessage, ModelResponse
from agent_prototype.execution.persistence.types import AgentOutput, RunMetadata
from agent_prototype.execution.runtime.types import AgentEvent, AgentState


def build_assistant_response(content=None, tool_calls=None) -> ModelResponse:
    """构造一个最小 assistant 响应。"""
    return ModelResponse(
        assistant_message=ChatMessage(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
        )
    )


def build_agent_output(
    reply: str,
    *,
    state: Optional[AgentState] = None,
    events: Optional[List[AgentEvent]] = None,
    session_id: str = "s",
    run_id: str = "r",
) -> AgentOutput:
    """构造一个最小 AgentOutput。"""
    return AgentOutput(
        reply=reply,
        state=state or AgentState(),
        events=events or [],
        metadata=RunMetadata(session_id=session_id, run_id=run_id),
    )
