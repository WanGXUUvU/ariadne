"""通用 Run 执行生命周期会话层。"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Literal, Optional, Union

from pydantic import BaseModel

from backend.core.types import StreamChunk, ModelUsage
from backend.execution.persistence.run_recorder import RunRecorder
from backend.execution.persistence.types import (
    RunInput,
    RunContext,
    RunFinalStatus,
    RunFinalizationInput,
)
from backend.execution.runtime.agent_runner import AgentRunner
from backend.execution.runtime.types import RunEvent, RunState

logger = logging.getLogger(__name__)


@dataclass
class RunLifecycleParams:
    """执行核心运行所需的最小物料。

    这是 RunLifecycle 的“动态执行上下文”。
    相比 RunContext 的稳定背景物料，这里还包含一次执行具体如何启动、如何续跑的控制参数。
    """

    # 稳定运行背景：state / definition / adapter / approval_policy / workspace 等。
    ctx: RunContext
    # 已装配好的智能体执行发动机。
    agent_runner: AgentRunner
    # 终态收口器；执行层只在结束时把 finalization input 交给它。
    recorder: RunRecorder
    # 本轮 run 的外部输入。
    run_input: RunInput
    # 当前 run 的唯一 ID。
    run_id: str
    # 工具开始执行时的副作用回调，一般来自 ToolTracer。
    on_tool_start: Optional[Callable[..., Any]] = None
    # 工具结束执行时的副作用回调。
    on_tool_finish: Optional[Callable[..., Any]] = None
    # 需要审批时的副作用回调。
    on_approval_required: Optional[Callable[..., Any]] = None
    # True 表示不要再往 state.messages 里补 user message；resume run 会用到。
    skip_user_message: bool = False
    # 事件编号起点；resume run 续跑时必须从旧 run 的下一个 index 接上。
    event_index: int = 0
    # 执行开始前就已经存在的正式事件；典型场景是 resume 先补一个 tool_result_event。
    initial_events: list[RunEvent] = field(default_factory=list)
    # True 表示本轮是 resume 续跑，而非新 run。
    is_resume: bool = False
    # True 表示本轮拥有 session 快照写入权；child run 会关掉。
    owns_session: bool = True


class RunLifecycleResultItem(BaseModel):
    """一次执行会话结束后的统一结果。"""

    status: RunFinalStatus
    reply: str
    events: list[RunEvent]
    state: RunState
    usage: Optional[ModelUsage] = None


class TextDeltaItem(BaseModel):
    """执行层产出的普通文本增量。"""

    type: Literal["text_delta"] = "text_delta"
    content: str


class ThinkingDeltaItem(BaseModel):
    """执行层产出的 thinking 文本增量。"""

    type: Literal["thinking_delta"] = "thinking_delta"
    content: str


class RunEventItem(BaseModel):
    """执行层产出的正式 RunEvent。"""

    type: Literal["run_event"] = "run_event"
    event: RunEvent


class RunStatusItem(BaseModel):
    """执行流终止信号，只携带终态，不含数据载荷。"""

    type: Literal["run_status"] = "run_status"
    status: RunFinalStatus


class UsageItem(BaseModel):
    """一次模型调用结束后返回的 token 用量。"""

    type: Literal["usage"] = "usage"
    model_call_index: int
    usage: ModelUsage


RunLifecycleItem = Union[
    TextDeltaItem,
    ThinkingDeltaItem,
    RunEventItem,
    RunStatusItem,
    UsageItem,
]


class RunLifecycle:
    """执行型 run 的共享生命周期容器。"""

    def __init__(self, params: RunLifecycleParams):
        self.params = params

    async def iterate(self) -> AsyncIterator[RunLifecycleItem]:
        """执行共享主循环，并实时产出通用执行项。"""
        reply_text = ""
        thinking_buf = ""
        events: list[RunEvent] = list(self.params.initial_events)
        usage_count = 0

        async def _flush_thinking() -> AsyncIterator[RunLifecycleItem]:
            """把累计的 thinking 文本收束成一个正式事件。"""
            nonlocal thinking_buf
            if thinking_buf:
                event = RunEvent(
                    index=len(events),
                    type="thinking",
                    content=thinking_buf,
                )
                events.append(event)
                thinking_buf = ""
                yield RunEventItem(event=event)

        try:
            async for item in self.params.agent_runner.async_stream_run(
                self.params.run_input,
                on_tool_start=self.params.on_tool_start,
                on_tool_finish=self.params.on_tool_finish,
                on_approval_required=self.params.on_approval_required,
                skip_user_message=self.params.skip_user_message,
                event_index=self.params.event_index,
                run_id=self.params.run_id,
                workspace_path=self.params.ctx.workspace_path,
            ):
                if isinstance(item, str):
                    # 普通文本增量：一边累积，一边实时往上 yield。
                    reply_text += item
                    yield TextDeltaItem(content=item)

                elif isinstance(item, StreamChunk) and item.type == "thinking_delta":
                    # thinking 增量先累计，再由 _flush_thinking 收成正式事件。
                    chunk = item.thinking_delta or ""
                    thinking_buf += chunk
                    yield ThinkingDeltaItem(content=chunk)

                elif isinstance(item, StreamChunk) and item.type == "done" and item.usage:
                    usage_count += 1
                    yield UsageItem(
                        model_call_index=usage_count,
                        usage=item.usage,
                    )

                elif isinstance(item, RunEvent):
                    if item.type in ("tool_result", "tool_error"):
                        reply_text = ""
                    async for flushed in _flush_thinking():
                        yield flushed
                    events.append(item)
                    yield RunEventItem(event=item)

            async for flushed in _flush_thinking():
                yield flushed

            # 正常结束后，如果包含 approval_required，则视为 paused。
            status = (
                RunFinalStatus.PAUSED
                if any(event.type == "approval_required" for event in events)
                else RunFinalStatus.COMPLETED
            )

            self.params.recorder.finalize_run(
                self._build_finalization(
                    status=status,
                    events=events,
                    reply=reply_text,
                )
            )

            yield RunStatusItem(status=status)

        except GeneratorExit, asyncio.CancelledError:
            async for flushed in _flush_thinking():
                yield flushed

            try:
                self.params.recorder.finalize_run(
                    self._build_finalization(
                        status=RunFinalStatus.CANCELLED,
                        events=events,
                        reply=reply_text,
                    )
                )
            except Exception:
                logger.exception(
                    "Failed to persist cancelled run during generator close: session_id=%s run_id=%s",
                    self.params.run_input.session_id,
                    self.params.run_id,
                )
            raise

        except Exception:
            async for flushed in _flush_thinking():
                yield flushed

            self.params.recorder.finalize_run(
                self._build_finalization(
                    status=RunFinalStatus.FAILED,
                    events=events,
                    reply=reply_text,
                )
            )
            raise

    def _build_finalization(
        self,
        *,
        status: RunFinalStatus,
        events: list[RunEvent],
        reply: str,
    ) -> RunFinalizationInput:
        """把本次执行结果转换成统一终态输入。"""
        return RunFinalizationInput(
            session_id=self.params.run_input.session_id,
            run_id=self.params.run_id,
            status=status,
            user_input=self.params.run_input.user_input,
            reply=reply,
            agent_name=self.params.ctx.effective_agent_name,
            events=events,
            state=self.params.agent_runner.state,
            usage=getattr(self.params.agent_runner, "last_usage", None),
            is_resume=self.params.is_resume,
            owns_session=self.params.owns_session,
        )

    def execute_sync(self) -> RunLifecycleResultItem:
        """同步消费入口。

        sync run / child run 仍然优先复用 AgentRunner.execute()，
        避免把只支持同步 generate 的适配器强行塞进异步流式链路。
        """
        try:
            output = self.params.agent_runner.execute(
                self.params.run_input,
                run_id=self.params.run_id,
            )
        except Exception:
            raise

        self.params.recorder.finalize_run(
            self._build_finalization(
                status=RunFinalStatus.COMPLETED,
                events=output.events,
                reply=output.reply,
            )
        )
        return RunLifecycleResultItem(
            status=RunFinalStatus.COMPLETED,
            reply=output.reply,
            events=output.events,
            state=output.state,
            usage=output.usage,
        )
