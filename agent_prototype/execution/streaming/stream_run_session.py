"""流式运行会话 (StreamRunSession)

职责：封装单次 SSE 流式 run 的完整生命周期。
  - 输入：已构建好的 ctx / observer / agent / persist 依赖
  - 输出：async 生成器，逐帧 yield SSE 字符串
  - 不感知 HTTP、不感知数据库连接，只调用已注入的协作对象

上游：RunService.async_stream_agent 负责组装依赖并调用 session.run()
下游：_sse_frame / StreamFrame 构造 SSE 字符串
"""

# ── 标准库 ────────────────────────────────────────────────────────────────────
import logging
import asyncio
from typing import AsyncIterator, List

logger = logging.getLogger(__name__)

# ── 本地模块 ──────────────────────────────────────────────────────────────────
from agent_prototype.core.types import ModelStreamEvent
from agent_prototype.execution.runtime.types import AgentEvent
from agent_prototype.execution.persistence.types import (
    AgentInput,
    RunFinalizationInput,
    RunFinalStatus,
)
from agent_prototype.execution.streaming.types import StreamFrame
from agent_prototype.execution.streaming.sse import _sse_frame
from agent_prototype.execution.runtime.agent_runtime import AgentRunner
from agent_prototype.observation.tool_run_observer import ToolRunObserver
from agent_prototype.execution.persistence.types import RunContext
from agent_prototype.execution.persistence.service import RunPersistenceService


class StreamRunSession:
    """这是一个“流式运行大舞台（执行容器）”。
    它主要负责管理单次流式运行（SSE）的完整生命周期。
    它不直接读写数据库，而是作为一个纯粹的舞台监督，拉起智能体发动机（AgentRunner），
    把产生的文本片段、思维链（Thinking）片段、工具调用等实时 yield 给前端 SSE 帧。
    如果中途发生了审批暂停、运行成功或者运行出错被突然中止，它会负责找 observer 或落库小助手（persist）来善后保存数据。
    """

    def __init__(
        self,
        ctx: RunContext,
        observer: ToolRunObserver,
        agent: AgentRunner,
        run_id: str,
        agent_input: AgentInput,
        persist: RunPersistenceService,
    ):
        """初始化流式运行舞台，把组装好的一切协作道具和依赖（物料、观察者、智能体、落库小助手）全部准备就绪。

        需要拿到的东西：
        - ctx: 装配好的运行时物料 RunContext。
        - observer: 工具运行观察者，负责工具执行阶段的数据感知与审批中间落库。
        - agent: 驱动本次运行的智能体 Runner 实例。
        - run_id: 本次运行的唯一 ID。
        - agent_input: 用户的输入参数。
        - persist: 用于最终落库的持久化服务。
        """
        self.ctx = ctx
        self.observer = observer
        self.agent = agent
        self.run_id = run_id
        self.agent_input = agent_input
        self.persist = persist

    async def run(self) -> AsyncIterator[str]:
        """流式运行主循环。"""
        partial_reply = ""
        thinking_buf = ""
        events: list[AgentEvent] = []

        def _flush_thinking() -> None:
            nonlocal thinking_buf
            if thinking_buf:
                events.append(
                    AgentEvent(
                        index=len(events),
                        type="thinking",
                        content=thinking_buf,
                    )
                )
                thinking_buf = ""

        try:
            yield self._start_frame()
            async for item in self.agent.async_stream_run(
                self.agent_input,
                on_tool_start=self.observer.on_tool_start,
                on_tool_finish=self.observer.on_tool_finish,
                on_approval_required=self.observer.on_approval_required,
                run_id=self.run_id,
                workspace_path=self.ctx.workspace_path,
            ):
                if isinstance(item, str):
                    partial_reply += item
                    yield _sse_frame(StreamFrame(type="delta", data={"content": item}))
                elif isinstance(item, ModelStreamEvent) and item.type == "thinking_delta":
                    thinking_buf += item.thinking_delta or ""
                    yield _sse_frame(
                        StreamFrame(
                            type="thinking_delta",
                            data={"content": item.thinking_delta or ""},
                        )
                    )
                elif isinstance(item, AgentEvent):
                    if item.type == "tool_progress":
                        yield _sse_frame(StreamFrame(type="agent_event", data=item.model_dump()))
                    else:
                        _flush_thinking()
                        events.append(item)
                        yield _sse_frame(StreamFrame(type="agent_event", data=item.model_dump()))

            _flush_thinking()
            paused = any(e.type == "approval_required" for e in events)

            if paused:
                self.persist.finalize_run(
                    self._build_finalization(
                        status=RunFinalStatus.PAUSED,
                        events=events,
                        partial_reply=partial_reply,
                    )
                )
                yield _sse_frame(StreamFrame(type="paused", data={"run_id": self.run_id}))
            else:
                metadata = self.persist.finalize_run(
                    self._build_finalization(
                        status=RunFinalStatus.COMPLETED,
                        events=events,
                        partial_reply=partial_reply,
                    )
                )
                yield _sse_frame(
                    StreamFrame(
                        type="end",
                        data={
                            "reply": partial_reply,
                            "state": self.agent.state.model_dump(),
                            "metadata": metadata.model_dump(),
                        },
                    )
                )

        except (GeneratorExit, asyncio.CancelledError):
            _flush_thinking()
            try:
                self.persist.finalize_run(
                    self._build_finalization(
                        status=RunFinalStatus.CANCELLED,
                        events=events,
                        partial_reply=partial_reply,
                    )
                )
            except Exception:
                logger.exception(
                    "Failed to persist cancelled run: session_id=%s run_id=%s",
                    self.agent_input.session_id,
                    self.run_id,
                )
            raise

        except Exception:
            _flush_thinking()
            try:
                self.persist.finalize_run(
                    self._build_finalization(
                        status=RunFinalStatus.FAILED,
                        events=events,
                        partial_reply=partial_reply,
                    )
                )
            except Exception:
                logger.exception(
                    "Failed to persist failed run: session_id=%s run_id=%s",
                    self.agent_input.session_id,
                    self.run_id,
                )
            raise

    # ── 私有帧构造 ────────────────────────────────────────────────────────────

    def _start_frame(self) -> str:
        """内部方法：生产戏开场的“帷幕拉开（start）”帧。
        通知前端，我们现在要开始针对哪个会话、哪个运行 ID 进行流式输出了。

        会给出来的结果：
        - 一个以 `data: ` 开头并以双换行符结尾的 start 帧字符串。
        """
        return _sse_frame(
            StreamFrame(
                type="start",
                data={
                    "session_id": self.agent_input.session_id,
                    "run_id": self.run_id,
                    "agent_name": self.ctx.effective_agent_name,
                    "skill_name": self.agent_input.skill_name,
                },
            )
        )

    def _build_finalization(
        self,
        *,
        status: RunFinalStatus,
        events: List[AgentEvent],
        partial_reply: str,
    ) -> RunFinalizationInput:
        return RunFinalizationInput(
            session_id=self.agent_input.session_id,
            run_id=self.run_id,
            status=status,
            user_input=self.agent_input.user_input,
            partial_reply=partial_reply,
            agent_name=self.ctx.effective_agent_name,
            skill_name=self.agent_input.skill_name,
            events=events,
            state=self.agent.state,
            usage=self.agent.last_usage,
            session_type=self.ctx.session_type,
        )