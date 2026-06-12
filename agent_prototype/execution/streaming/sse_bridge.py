"""流式运行会话 (RunSSEBridge)

职责：
- 作为 stream run 的外层 adapter，把通用执行层结果翻译成 SSE。
- 负责 start / delta / thinking_delta / agent_event / paused / end 帧输出。

不负责：
- 不负责执行主循环。
- 不负责终态持久化分发。
"""

import logging
from typing import AsyncIterator

logger = logging.getLogger(__name__)

from agent_prototype.execution.persistence.run_recorder import RunRecorder
from agent_prototype.execution.persistence.types import AgentInput, RunContext, RunFinalStatus, RunMetadata
from agent_prototype.execution.runtime.agent_runtime import AgentRunner
from agent_prototype.execution.runtime.run_lifecycle import (
    AgentEventItem,
    FinalResultItem,
    RunLifecycleParams,
    RunLifecycle,
    TextDeltaItem,
    ThinkingDeltaItem,
)
from agent_prototype.execution.streaming.sse import _sse_frame
from agent_prototype.execution.streaming.types import StreamFrame
from agent_prototype.observation.tool_tracer import ToolTracer


class RunSSEBridge:
    """stream run 的协议适配壳层。"""

    def __init__(
        self,
        ctx: RunContext,
        observer: ToolTracer,
        agent_runner: AgentRunner,
        run_id: str,
        agent_input: AgentInput,
        persist: RunRecorder,
    ):
        self.ctx = ctx
        self.observer = observer
        self.agent_runner = agent_runner
        self.run_id = run_id
        self.agent_input = agent_input
        self.persist = persist

    async def stream(self) -> AsyncIterator[str]:
        """消费通用执行项，并实时翻译成 SSE。"""
        yield self._start_frame()

        session = RunLifecycle(
            RunLifecycleParams(
                ctx=self.ctx,
                agent_runner=self.agent_runner,
                persist=self.persist,
                agent_input=self.agent_input,
                run_id=self.run_id,
                on_tool_start=self.observer.on_tool_start,
                on_tool_finish=self.observer.on_tool_finish,
                on_approval_required=self.observer.on_approval_required,
            )
        )

        try:
            async for item in session.iterate():
                if isinstance(item, TextDeltaItem):
                    yield _sse_frame(
                        StreamFrame(
                            type="delta",
                            data={"content": item.content},
                        )
                    )

                elif isinstance(item, ThinkingDeltaItem):
                    yield _sse_frame(
                        StreamFrame(
                            type="thinking_delta",
                            data={"content": item.content},
                        )
                    )

                elif isinstance(item, AgentEventItem):
                    yield _sse_frame(
                        StreamFrame(
                            type="agent_event",
                            data=item.event.model_dump(),
                        )
                    )

                elif isinstance(item, FinalResultItem):
                    if item.result.status == RunFinalStatus.PAUSED:
                        yield _sse_frame(
                            StreamFrame(
                                type="paused",
                                data={"run_id": self.run_id},
                            )
                        )
                    else:
                        yield _sse_frame(
                            StreamFrame(
                                type="end",
                                data={
                                    "reply": item.result.partial_reply,
                                    "state": item.result.state.model_dump(),
                                    "metadata": RunMetadata(
                                        session_id=self.agent_input.session_id,
                                        run_id=self.run_id,
                                        agent_name=self.ctx.effective_agent_name,
                                    ).model_dump(),
                                },
                            )
                        )
        except Exception:
            logger.exception(
                "Stream run failed: session_id=%s run_id=%s",
                self.agent_input.session_id,
                self.run_id,
            )
            raise

    def _start_frame(self) -> str:
        """start 帧由 stream adapter 自己生成。"""
        return _sse_frame(
            StreamFrame(
                type="start",
                data={
                    "session_id": self.agent_input.session_id,
                    "run_id": self.run_id,
                    "agent_name": self.ctx.effective_agent_name,
                },
            )
        )
