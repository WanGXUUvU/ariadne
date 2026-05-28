"""
[九层模型 - L8 执行引擎层 (Execution Layer)]

文件职责：
- 充当运行时核心业务流编排与引擎层（RunService）。
- 整合 RunContext 构建、AgentRunner 同步/流式运行驱动、以及物理持久化落库。
- 构建并闭包包装三个“三纯回调函数”（派发器、查询器、等待器），将其动态注入至 ToolRegistry，从而完美实现工具层与执行引擎的解耦。
- 实现线程安全的异步后台工作器（_run_child_worker）来调度物理子任务线程。

上游依赖：L10 接口层 (GET/POST 路由控制器)。
下游依赖：L8 上下文构建器 (run_context_builder.py)、L8 运行载体 (agent_runtime.py)、L3 工具注册中心 (ToolRegistry)。
"""
# ── 标准库 ────────────────────────────────────────────────────────────────────
import uuid
from typing import AsyncIterator, Optional, Callable

# ── 第三方库 ──────────────────────────────────────────────────────────────────
from sqlalchemy.orm import Session

# ── 本地模块 ──────────────────────────────────────────────────────────────────
from agent_prototype.observation.tool_run_observer import ToolRunObserver
from agent_prototype.security.approval.store import SqliteApprovalStore
from agent_prototype.memory.session.store import SqliteSessionStore
from agent_prototype.memory.run.store import SqliteRunStore
from agent_prototype.core.types import ModelStreamEvent
from agent_prototype.tools.registry import build_run_registry
from agent_prototype.core.types import (
    AgentEvent, AgentInput, AgentOutput, AgentState, RunMetadata,
)
from agent_prototype.execution.streaming.types import StreamFrame
from agent_prototype.execution.runtime.agent_runtime import AgentRunner
from agent_prototype.execution.runtime.agent_executor import _executor, _global_futures
from agent_prototype.execution.persistence.builder import RunContextBuilder
from agent_prototype.execution.persistence.service import RunPersistenceService
from agent_prototype.execution.streaming.stream_run_session import StreamRunSession


class RunService:
    """这是整个智能体系统的“运行时总指挥官”。
    它主要负责协调和调度智能体的实际运行。比如：准备物料（RunContextBuilder）、启动智能体（AgentRunner）、
    管理子智能体的并发调用（多线程派发、状态查询、阻塞等待）、并且在完事之后指挥落库小助手（RunPersistenceService）把数据保存下来。
    """

    def __init__(self, db: Session):
        """初始化总指挥官，给他分配好数据库连接、会话存储、审批记录存储和落库小助手。

        需要拿到的东西：
        - db: 数据库连接会话对象。
        """
        self.db            = db
        self.store         = SqliteSessionStore(db)
        self._run_store    = SqliteRunStore(db)
        self.approval_store = SqliteApprovalStore(db)
        self.persist       = RunPersistenceService(db)

    # ── 私有辅助 ──────────────────────────────────────────────────────────────

    def _make_child_dispatcher(self, parent_run_id: str, session_id: str) -> Callable[[str, str], str]:
        """内部方法：生产一个“子智能体派发器”。
        当大模型觉得任务太复杂，需要雇佣一个“子智能体（小弟）”去独立干活时，这个派发器就会在后台默默启动一个新线程来跑小弟的任务。

        需要拿到的东西：
        - parent_run_id: 派发这个小弟的老大（父级）运行 ID。
        - session_id: 当前会话的 ID。

        会给出来的结果：
        - 一个可执行的闭包函数（Child Dispatcher），大模型调工具的时候直接调用它来派发新任务，并拿到小弟的运行 ID。
        """
        def child_dispatcher(task: str, agent_name: str = "子Agent") -> str:
            child_run_id = uuid.uuid4().hex
            
            # 将异步运行子 Agent 任务提交至全局线程池中执行
            future = _executor.submit(
                self._run_child_worker,
                task=task,
                child_run_id=child_run_id,
                parent_run_id=parent_run_id,
                session_id=session_id,
                agent_name=agent_name,
            )
            _global_futures[child_run_id] = future
            return child_run_id
        return child_dispatcher

    def _make_status_checker(self) -> Callable[[list[str]], dict]:
        """内部方法：生产一个“小弟工作进度查询器”。
        老大派发了小弟干活之后，可以通过这个查询器，随时去看看这批小弟到底是干完了、还在跑、还是出错了。

        会给出来的结果：
        - 一个可执行的闭包函数（Status Checker），输入一堆小弟的 ID，吐出这批小弟当前的工作状态和结果。
        """
        def status_checker(child_run_ids: list[str]) -> dict:
            result = {}
            for run_id in child_run_ids:
                if run_id not in _global_futures:
                    result[run_id] = {"status": "not_found"}
                    continue

                f = _global_futures[run_id]
                if f.done():
                    if f.exception():
                        result[run_id] = {"status": "error", "error": str(f.exception())}
                    else:
                        result[run_id] = {"status": "done", "reply": f.result().reply}
                else:
                    result[run_id] = {"status": "running"}
            return result
        return status_checker

    def _make_child_waiter(self) -> Callable[[str], str]:
        """内部方法：生产一个“催活专员”。
        当老大必须拿到某个小弟的工作结果才能继续往下走时，这个专员就会死等（阻塞等待最多 120 秒），直到小弟干完并把结果交出来。

        会给出来的结果：
        - 一个可执行的闭包函数（Child Waiter），输入一个小弟的 ID，如果小弟顺利干完就返回他的答复纯文本；如果超时或者出错就抛出异常。
        """
        def child_waiter(child_run_id: str) -> str:
            f = _global_futures.get(child_run_id)
            if f is None:
                raise LookupError(f"child_run_id {child_run_id} not found")
            
            # 这里调用 result(timeout=120) 会阻塞等待 120s，超时抛出 TimeoutError，失败则抛出对应异常
            output = f.result(timeout=120)
            return output.reply
        return child_waiter

    def _run_child_worker(
        self,
        task: str,
        child_run_id: str,
        parent_run_id: str,
        session_id: str,
        agent_name: str = "子Agent"
    ):
        """这才是子智能体（小弟）在后台默默流汗干活的“实际车间方法”！
        因为是在单独的后台线程里跑，所以它会自己开一个干净的数据库连接，启动一个全新的 AgentRunner，
        跑完之后还会把小弟的运行痕痕迹和产生的所有事件老老实实写进数据库，最后自动把数据库连接关掉。

        需要拿到的东西：
        - task: 分配给小弟的任务纯文本。
        - child_run_id: 这个小弟的运行 ID。
        - parent_run_id: 老大的运行 ID。
        - session_id: 会话 ID。
        - agent_name: 小弟的代号/名字（默认叫 "子Agent"）。

        会给出来的结果：
        - 小弟运行完之后的 AgentOutput 输出结果对象。
        """
        from agent_prototype.infra.db.engine import SessionLocal
        from agent_prototype.core.types import AgentDefinition
        
        # ⚠️ 注意：子智能体运行于独立线程，必须使用单独的物理 DB Session
        db = SessionLocal()
        try:
            adapter = RunContextBuilder(db).build_adapter(session_id)
            child_state = AgentState()
            definition = AgentDefinition(id=child_run_id, name=agent_name)
            
            agent = AgentRunner(
                state=child_state,
                definition=definition,
                model_adapter=adapter,
                # 子 Agent 递归支持工具箱，并且同样采用闭包回调隔离依赖
                tool_registry=build_run_registry(
                    child_dispatcher=self._make_child_dispatcher(child_run_id, session_id),
                    status_checker=self._make_status_checker(),
                    child_waiter=self._make_child_waiter(),
                )
            )
            output = agent.run(AgentInput(
                session_id=session_id,
                user_input=task,
            ))

            # 📍 落库：子 Agent 的 run 记录 + 事件列表，挂在同一个 session 下
            store = SqliteRunStore(db)
            store.create_child_run(
                parent_run_id=parent_run_id,
                session_id=session_id,
                run_id=child_run_id,
                agent_name=agent_name,
                user_input=task,
                reply=output.reply,
                events=output.events,
            )
            db.commit()
            return output
        except Exception as e:
            db.rollback()
            print(f"Failed to persist child run {child_run_id}: {e}")
            raise
        finally:
            db.close()

    def _build_agent_runner(self, ctx, run_id: str, agent_input: AgentInput) -> AgentRunner:
        """内部组装方法：把智能体底座（AgentRunner）给捏出来。
        它会把大模型的适配器、人设定义、审批规则全给它，最重要的是会把“派发小弟、查询进度、催活”这三个闭包锦囊妙计塞给它，实现解耦。

        需要拿到的东西：
        - ctx: 装配好的 RunContext 运行物料背包。
        - run_id: 这次运行的 ID。
        - agent_input: 输入的参数对象。

        会给出来的结果：
        - 一个组装完毕、随时可以开始跑的 AgentRunner 实例。
        """
        return AgentRunner(
            state=ctx.state,
            definition=ctx.definition,
            allow_tool_names=ctx.definition.tool_names,
            model_adapter=ctx.adapter,
            # 核心解耦点：通过注入三个“三纯”回调将工具层与底座执行细节彻底解耦
            tool_registry=build_run_registry(
                child_dispatcher=self._make_child_dispatcher(run_id, agent_input.session_id),
                status_checker=self._make_status_checker(),
                child_waiter=self._make_child_waiter(),
            ),
            approval_policy=ctx.approval_policy,
        )

    # ── 公开方法 ──────────────────────────────────────────────────────────────

    def run_agent(self, agent_input: AgentInput) -> AgentOutput:
        """同步普通运行主入口：一口气让智能体从头跑到尾！
        会先打包好运行时物料，组装出智能体底座，让它一口气跑完，最后再把所有的聊天数据和 Token 消耗都写进数据库，返回最终结果。

        需要拿到的东西：
        - agent_input: 用户请求的输入参数。

        会给出来的结果：
        - 包含最终聊天答复和状态的 AgentOutput 输出结果。
        """
        run_id = uuid.uuid4().hex
        ctx = RunContextBuilder(self.db).build(agent_input)
        agent = self._build_agent_runner(ctx, run_id, agent_input)

        output = agent.run(agent_input)
        output.state.agent_name = ctx.effective_agent_name
        return self.persist.save_completed(
            agent_input=agent_input,
            output=output,
            effective_agent_name=ctx.effective_agent_name,
            run_id=run_id,
            usage=output.usage,
            session_type=ctx.session_type,
        )

    async def async_stream_agent(self, agent_input: AgentInput) -> AsyncIterator[str]:
        """异步流式运行主入口：像挤牙膏一样，把智能体的思考过程和回答实时吐给前端（SSE 格式）！
        支持高并发、中间需要审批时会中断等待、并且能在调工具的中间状态也进行数据落库。

        需要拿到的东西：
        - agent_input: 用户请求的输入参数。

        会给出来的结果：
        - 一个异步迭代器，实时吐出 StreamFrame 的字符串帧。
        """
        run_id   = uuid.uuid4().hex
        ctx      = RunContextBuilder(self.db).build(agent_input)
        observer = ToolRunObserver(self.db, self._run_store, self.approval_store,
                                    agent_input.session_id, run_id, agent_input)
        agent    = self._build_agent_runner(ctx, run_id, agent_input)
        async for frame in StreamRunSession(ctx, observer, agent, run_id, agent_input, self.persist).run():
            yield frame

    def finalize_run(
        self,
        session_id: str,
        run_id: str,
        user_input: str,
        partial_reply: str,
        agent_name: Optional[str],
        skill_name: Optional[str],
    ) -> dict:
        """当运行被突然中止时，紧急调用落库小助手的 save_cancelled 来善后，保存残缺的半成品数据并把状态更新为取消。

        需要拿到的东西：
        - session_id: 会话 ID。
        - run_id: 运行 ID。
        - user_input: 用户的本轮输入。
        - partial_reply: 中断时已经吐出来的半成品回复。
        - agent_name: 智能体名字。
        - skill_name: 使用的技能名字。

        会给出来的结果：
        - 一个简单的成功字典，比如 `{"ok": True}`。
        """
        return self.persist.save_cancelled(
            session_id, run_id, user_input, partial_reply, agent_name, skill_name,
        )

    def get_run_detail(self, session_id: str, run_id: str):
        """查账！去数据库查某次具体运行的详情（如智能体的回答和调用过的工具）。

        需要拿到的东西：
        - session_id: 会话 ID。
        - run_id: 运行 ID。

        会给出来的结果：
        - 包含运行详情和工具调用的元组。
        """
        return self.persist.get_run_detail(session_id, run_id)

    def get_session_trace(self, session_id: str, run_id: Optional[str] = None):
        """读取会话的执行轨迹（Trace），包含所有运行记录及事件详情。

        需要拿到的东西：
        - session_id: 会话 ID。
        - run_id: 可选的运行 ID，不传则返回该会话下所有运行的轨迹。

        会给出来的结果：
        - 一个元组 (run_records, events_map)，如果无记录则返回 ([], {})。
        """
        import json
        from agent_prototype.core.types import ToolResult
        from agent_prototype.core.types import AgentEvent

        run_records = self._run_store.list_run_records(session_id, run_id=run_id)
        if not run_records:
            return [], {}

        events_map: dict[str, list[AgentEvent]] = {}
        for run_record in run_records:
            event_rows = self._run_store.list_run_events(run_record.run_id)
            events = []
            for row in event_rows:
                tool_result = None
                if row.tool_result_json:
                    tool_result = ToolResult.model_validate(json.loads(row.tool_result_json))
                events.append(AgentEvent(
                    index=row.event_index,
                    type=row.type,
                    content=row.content,
                    tool_name=row.tool_name,
                    tool_call_id=row.tool_call_id,
                    tool_result=tool_result,
                ))
            events_map[run_record.run_id] = events

        return run_records, events_map
