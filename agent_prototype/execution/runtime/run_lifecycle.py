"""通用 Run 执行生命周期会话层。"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Literal, Optional, Union

from pydantic import BaseModel

from agent_prototype.core.types import ModelStreamEvent, ModelUsage
from agent_prototype.execution.persistence.run_recorder import RunRecorder
from agent_prototype.execution.persistence.types import (
    AgentInput,
    RunContext,
    RunFinalStatus,
    RunFinalizationInput,
)
from agent_prototype.execution.runtime.agent_runtime import AgentRunner
from agent_prototype.execution.runtime.types import AgentEvent, AgentState

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
    persist: RunRecorder
    # 本轮 run 的外部输入。
    agent_input: AgentInput
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
    initial_events: list[AgentEvent] = field(default_factory=list)
    # True 表示本轮结束时要往已有 run 上追加事件，而不是新建一条 run trace。
    append_events: bool = False
    # 控制本轮 finalization 是否更新主 session snapshot；child run 会关掉。
    update_session_snapshot: bool = True


class RunLifecycleResult(BaseModel):
    """一次执行会话结束后的统一结果。"""

    status: RunFinalStatus
    partial_reply: str
    events: list[AgentEvent]
    state: AgentState
    usage: Optional[ModelUsage] = None


class TextDeltaItem(BaseModel):
    """执行层产出的普通文本增量。"""

    type: Literal["text_delta"] = "text_delta"
    content: str


class ThinkingDeltaItem(BaseModel):
    """执行层产出的 thinking 文本增量。"""

    type: Literal["thinking_delta"] = "thinking_delta"
    content: str


class AgentEventItem(BaseModel):
    """执行层产出的正式 AgentEvent。"""

    type: Literal["agent_event"] = "agent_event"
    event: AgentEvent


class FinalResultItem(BaseModel):
    """执行层最终结果项。"""

    type: Literal["final_result"] = "final_result"
    result: RunLifecycleResult


RunLifecycleItem = Union[
    TextDeltaItem,
    ThinkingDeltaItem,
    AgentEventItem,
    FinalResultItem,
]


class RunLifecycle:
    """执行型 run 的共享生命周期容器。"""

    def __init__(self, deps: RunLifecycleParams):
        self.deps = deps

    async def iterate(self) -> AsyncIterator[RunLifecycleItem]:
        """执行共享主循环，并实时产出通用执行项。"""
        partial_reply = ""
        thinking_buf = ""
        events: list[AgentEvent] = list(self.deps.initial_events)

        async def _flush_thinking() -> AsyncIterator[RunLifecycleItem]:
            """把累计的 thinking 文本收束成一个正式事件。"""
            nonlocal thinking_buf
            if thinking_buf:
                event = AgentEvent(
                    index=len(events),
                    type="thinking",
                    content=thinking_buf,
                )
                events.append(event)
                thinking_buf = ""
                yield AgentEventItem(event=event)

        try:
            async for item in self.deps.agent_runner.async_stream_run(
                self.deps.agent_input,
                on_tool_start=self.deps.on_tool_start,
                on_tool_finish=self.deps.on_tool_finish,
                on_approval_required=self.deps.on_approval_required,
                skip_user_message=self.deps.skip_user_message,
                event_index=self.deps.event_index,
                run_id=self.deps.run_id,
                workspace_path=self.deps.ctx.workspace_path,
            ):
                if isinstance(item, str):
                    # 普通文本增量：一边累积，一边实时往上 yield。
                    partial_reply += item
                    yield TextDeltaItem(content=item)

                elif isinstance(item, ModelStreamEvent) and item.type == "thinking_delta":
                    # thinking 增量先累计，再由 _flush_thinking 收成正式事件。
                    chunk = item.thinking_delta or ""
                    thinking_buf += chunk
                    yield ThinkingDeltaItem(content=chunk)

                elif isinstance(item, AgentEvent):
                    # tool_progress 不进入正式 events 列表，只透传给上层。
                    if item.type == "tool_progress":
                        yield AgentEventItem(event=item)
                    else:
                        async for flushed in _flush_thinking():
                            yield flushed
                        events.append(item)
                        yield AgentEventItem(event=item)

            async for flushed in _flush_thinking():
                yield flushed

            # 正常结束后，如果包含 approval_required，则视为 paused。
            status = (
                RunFinalStatus.PAUSED
                if any(e.type == "approval_required" for e in events)
                else RunFinalStatus.COMPLETED
            )

            self.deps.persist.finalize_run(
                self._build_finalization(
                    status=status,
                    events=events,
                    partial_reply=partial_reply,
                )
            )

            yield FinalResultItem(
                result=RunLifecycleResult(
                    status=status,
                    partial_reply=partial_reply,
                    events=events,
                    state=self.deps.agent_runner.state,
                    usage=self.deps.agent_runner.last_usage,
                )
            )

        except (GeneratorExit, asyncio.CancelledError):
            async for flushed in _flush_thinking():
                yield flushed

            try:
                self.deps.persist.finalize_run(
                    self._build_finalization(
                        status=RunFinalStatus.CANCELLED,
                        events=events,
                        partial_reply=partial_reply,
                    )
                )
            except Exception:
                logger.exception(
                    "Failed to persist cancelled run during generator close: session_id=%s run_id=%s",
                    self.deps.agent_input.session_id,
                    self.deps.run_id,
                )
            raise

        except Exception:
            async for flushed in _flush_thinking():
                yield flushed

            self.deps.persist.finalize_run(
                self._build_finalization(
                    status=RunFinalStatus.FAILED,
                    events=events,
                    partial_reply=partial_reply,
                )
            )
            raise

    def _build_finalization(
        self,
        *,
        status: RunFinalStatus,
        events: list[AgentEvent],
        partial_reply: str,
        state: Optional[AgentState] = None,
        usage: Optional[ModelUsage] = None,
    ) -> RunFinalizationInput:
        """把本次执行结果转换成统一终态输入。"""
        resolved_usage = usage if isinstance(usage, ModelUsage) else None
        if resolved_usage is None:
            candidate = getattr(self.deps.agent_runner, "last_usage", None)
            if isinstance(candidate, ModelUsage):
                resolved_usage = candidate
        return RunFinalizationInput(
            session_id=self.deps.agent_input.session_id,
            run_id=self.deps.run_id,
            status=status,
            user_input=self.deps.agent_input.user_input,
            partial_reply=partial_reply,
            agent_name=self.deps.ctx.effective_agent_name,
            events=events,
            state=state or self.deps.agent_runner.state,
            usage=resolved_usage,
            session_type=self.deps.ctx.session_type,
            append_events=self.deps.append_events,
            update_session_snapshot=self.deps.update_session_snapshot,
        )

    async def execute(self) -> RunLifecycleResult:
        """消费执行项流，只返回最终结果。"""
        async for item in self.run():
            if isinstance(item, FinalResultItem):
                return item.result
        raise RuntimeError("RunLifecycle finished without FinalResultItem")

    def execute_sync(self) -> RunLifecycleResult:
        """同步消费入口。

        sync run / child run 仍然优先复用 AgentRunner.execute()，
        避免把只支持同步 generate 的适配器强行塞进异步流式链路。
        """
        try:
            output = self.deps.agent_runner.execute(
                self.deps.agent_input,
                run_id=self.deps.run_id,
            )
        except Exception:
            raise

        self.deps.persist.finalize_run(
            self._build_finalization(
                status=RunFinalStatus.COMPLETED,
                events=output.events,
                partial_reply=output.reply,
                state=output.state,
                usage=output.usage,
            )
        )
        return RunLifecycleResult(
            status=RunFinalStatus.COMPLETED,
            partial_reply=output.reply,
            events=output.events,
            state=output.state,
            usage=output.usage,
        )
