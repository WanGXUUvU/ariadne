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
from agent_prototype.model.types.model_types import ModelStreamEvent
from agent_prototype.api.dto.schemas import (
    AgentEvent, AgentInput, AgentOutput, RunMetadata, StreamFrame,
)
from agent_prototype.execution.streaming.sse import _sse_frame
from agent_prototype.execution.runtime.agent_runtime import AgentRunner
from agent_prototype.observation.hooks.tool_run_observer import ToolRunObserver
from agent_prototype.execution.persistence.run_context_builder import RunContext
from agent_prototype.execution.persistence.run_persistence import RunPersistenceService


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
        self.ctx         = ctx
        self.observer    = observer
        self.agent       = agent
        self.run_id      = run_id
        self.agent_input = agent_input
        self.persist     = persist

    async def run(self) -> AsyncIterator[str]:
        """流式大戏开演！这是最核心的方法，会按顺序不断吐出 SSE 数据帧。
        在执行过程中，它会把大模型的思维过程（thinking_delta）和正文回复（delta）源源不断地挤出来，
        如果在执行工具时遇到审批阻碍，就会自动转入“审批挂起”状态；如果一路顺风顺利答完，就会完成并落库。
        如果在中途被强行中断（异常或取消），它会使用 `save_cancelled` 做好善后，绝对不丢失用户的输入。

        会给出来的结果：
        - 一个异步生成器迭代器，实时 yield 符合 SSE 协议的纯文本帧。
        """
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
        """内部方法：生产戏开场的“帷幕拉开（start）”帧。
        通知前端，我们现在要开始针对哪个会话、哪个运行 ID 进行流式输出了。

        会给出来的结果：
        - 一个以 `data: ` 开头并以双换行符结尾的 start 帧字符串。
        """
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
        """内部方法：当运行因为工具需要人工审批而暂停时，紧急通过 observer 观察者进行中间态快照落库，并生产一个“暂停（paused）”帧。

        需要拿到的东西：
        - events: 中断前已经产生的所有事件。
        - partial_reply: 中断前已经生成的半成品答复。

        会给出来的结果：
        - 告诉前端已暂停的 paused 帧字符串。
        """
        self.observer.handle_paused(self.agent.state, events, partial_reply)
        return _sse_frame(StreamFrame(type="paused", data={"run_id": self.run_id}))

    def _handle_completed(self, events: List[AgentEvent], partial_reply: str) -> str:
        """内部方法：当运行正常且顺利完成时，委托 persist 落库小助手把最终结果完整地写入数据库，并生产一个“谢幕（end）”帧。

        需要拿到的东西：
        - events: 运行中产生的所有完整事件。
        - partial_reply: 智能体的最终完整答复。

        会给出来的结果：
        - 告诉前端运行结束的 end 帧字符串（包含最终回复和元数据）。
        """
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
