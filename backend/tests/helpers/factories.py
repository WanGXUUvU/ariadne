"""测试假对象工厂。"""

from typing import List, Optional

from backend.core.types import ChatMessage, ModelResponse
from backend.execution.persistence.types import RunOutput, RunMetadata
from backend.execution.runtime.types import RunEvent, RunState


def build_assistant_response(content=None, tool_calls=None) -> ModelResponse:
    """构造一个最小 assistant 响应。"""
    return ModelResponse(
        assistant_message=ChatMessage(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
        )
    )


def build_run_output(
    reply: str,
    *,
    state: Optional[RunState] = None,
    events: Optional[List[RunEvent]] = None,
    session_id: str = "s",
    run_id: str = "r",
) -> RunOutput:
    """构造一个最小 RunOutput。"""
    return RunOutput(
        reply=reply,
        state=state or RunState(),
        events=events or [],
        metadata=RunMetadata(session_id=session_id, run_id=run_id),
    )
