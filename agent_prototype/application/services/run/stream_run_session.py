"""流式运行会话 (StreamRunSession)

职责：封装单次 SSE 流式 run 的完整生命周期。
  - 输入：已构建好的 ctx / observer / agent / persist 依赖
  - 输出：async 生成器，逐帧 yield SSE 字符串
  - 不感知 HTTP、不感知数据库连接，只调用已注入的协作对象

上游：RunService.async_stream_agent 负责组装依赖并调用 session.run()
下游：_sse_frame / StreamFrame 构造 SSE 字符串
"""

# ── 标准库 ────────────────────────────────────────────────────────────────────
from typing import AsyncIterator, List

# ── 本地模块 ──────────────────────────────────────────────────────────────────
from agent_prototype.infrastructure.llm.model_types import ModelStreamEvent
from agent_prototype.interface.dto.schemas import (
    AgentEvent, AgentInput, AgentOutput, RunMetadata, StreamFrame,
)
from agent_prototype.application.runtime.sse_utils import _sse_frame
from agent_prototype.application.runtime.agent_runtime import AgentRunner
from agent_prototype.application.runtime.tool_run_observer import ToolRunObserver
from agent_prototype.application.services.run.run_context_builder import RunContext
from agent_prototype.application.services.run.run_persistence import RunPersistenceService


class StreamRunSession:
    """单次流式 run 的执行容器。

    由 RunService 组装依赖后调用 ``run()``，本类不持有 db / store 引用，
    所有副作用通过 observer 和 persist 委托出去。
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
        self.ctx         = ctx
        self.observer    = observer
        self.agent       = agent
        self.run_id      = run_id
        self.agent_input = agent_input
        self.persist     = persist

    async def run(self) -> AsyncIterator[str]:
        """完整流式执行，按序 yield SSE 帧。异常时自动标记 cancelled。"""
        completed       = False
        partial_reply   = ""
        thinking_buf    = ""   # 当前轮次的 thinking 内容，遇到 AgentEvent 时 flush 进 events
        events: list[AgentEvent] = []

        def _flush_thinking() -> None:
            """把当前积累的 thinking_buf 作为一条事件追加到 events，然后清空 buf。
            在每个 AgentEvent（工具调用/结果）入队前调用，保证 thinking 位于对应工具调用之前。"""
            nonlocal thinking_buf
            if thinking_buf:
                events.append(AgentEvent(
                    index=len(events),
                    type="thinking",
                    content=thinking_buf,
                ))
                thinking_buf = ""

        try:
            yield self._start_frame()
            async for item in self.agent.async_stream_run(
                self.agent_input,
                on_tool_start=self.observer.on_tool_start,
                on_tool_finish=self.observer.on_tool_finish,
                on_approval_required=self.observer.on_approval_required,
                run_id=self.run_id,
                workspace_path=self.ctx.workspace_path
            ):
                if isinstance(item, str):
                    partial_reply += item
                    yield _sse_frame(StreamFrame(type="delta", data={"content": item}))
                elif isinstance(item, ModelStreamEvent) and item.type == "thinking_delta":
                    thinking_buf += item.thinking_delta or ""
                    yield _sse_frame(StreamFrame(type="thinking_delta", data={"content": item.thinking_delta or ""}))
                elif isinstance(item, AgentEvent):
                    # 先 flush 当前 thinking，保证 thinking 排在此事件之前
                    _flush_thinking()
                    events.append(item)
                    yield _sse_frame(StreamFrame(type="agent_event", data=item.model_dump()))

            # 循环正常结束：flush 最后一轮 thinking（最终回答前的思考，无后续工具调用）
            _flush_thinking()
            paused = any(e.type == "approval_required" for e in events)
            if paused:
                yield self._handle_paused(events, partial_reply)
            else:
                yield self._handle_completed(events, partial_reply)
            completed = True

        finally:
            if not completed:
                try:
                    # abort 时 async for 中断，_flush_thinking() 未被调用，
                    # 在此补做：把当前轮次未 flush 的 thinking 追加为事件。
                    _flush_thinking()
                    self.persist.save_cancelled(
                        self.agent_input.session_id,
                        self.run_id,
                        self.agent_input.user_input,
                        partial_reply,
                        self.ctx.effective_agent_name,
                        self.agent_input.skill_name,
                        events=events,
                    )
                except Exception:
                    pass

    # ── 私有帧构造 ────────────────────────────────────────────────────────────

    def _start_frame(self) -> str:
        return _sse_frame(StreamFrame(
            type="start",
            data={
                "session_id": self.agent_input.session_id,
                "run_id":     self.run_id,
                "agent_name": self.ctx.effective_agent_name,
                "skill_name": self.agent_input.skill_name,
            }
        ))

    def _handle_paused(self, events: List[AgentEvent], partial_reply: str) -> str:
        """审批中断：委托 observer 落库，返回 paused 帧。"""
        self.observer.handle_paused(self.agent.state, events, partial_reply)
        return _sse_frame(StreamFrame(type="paused", data={"run_id": self.run_id}))

    def _handle_completed(self, events: List[AgentEvent], partial_reply: str) -> str:
        """正常完成：委托 persist 落库，返回 end 帧。"""
        output = AgentOutput(
            reply=partial_reply,
            state=self.agent.state,
            events=events,
            metadata=RunMetadata(
                session_id=self.agent_input.session_id,
                run_id=self.run_id,
                agent_name=self.ctx.effective_agent_name,
                skill_name=self.agent_input.skill_name,
            )
        )
        output.state.agent_name = self.ctx.effective_agent_name
        self.persist.save_completed(
            agent_input=self.agent_input,
            output=output,
            effective_agent_name=self.ctx.effective_agent_name,
            run_id=self.run_id,
            usage=self.agent.last_usage,
            session_type=self.ctx.session_type,
        )
        return _sse_frame(StreamFrame(
            type="end",
            data={
                "reply":    partial_reply,
                "state":    self.agent.state.model_dump(),
                "metadata": output.metadata.model_dump(),
            }
        ))
