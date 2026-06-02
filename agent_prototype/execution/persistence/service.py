"""Run 落库服务。

职责：
- 正常完成时保存快照、trace、刷新状态
- 异常中断时兜底存储 partial run
- 查询 run 详情
上游：RunService 调用
下游：SqliteSessionStore
"""

from typing import Optional
from sqlalchemy.orm import Session

from agent_prototype.memory.session.store import SqliteSessionStore
from agent_prototype.memory.run.store import SqliteRunStore
from agent_prototype.core.types import ModelUsage, ChatMessage
from agent_prototype.execution.persistence.types import AgentInput, AgentOutput, RunMetadata
from agent_prototype.execution.runtime.types import AgentState
from agent_prototype.execution.streaming.sse import build_reply_preview


class RunPersistenceService:
    """这是一个“数据落库小助手（持久化服务）”。
    它的工作非常单纯，就是负责把智能体运行的最终结果（无论是顺利跑完、中途取消、还是审批通过后恢复运行）给老老实实地保存到数据库里，
    同时在需要的时候，能帮我们从数据库里把运行的详情信息给查出来。
    """

    def __init__(self, db: Session):
        """初始化落库小助手，给他分配数据库连接和 SQLite 存储仓库。

        需要拿到的东西：
        - db: 数据库连接会话对象。
        """
        self.db = db
        self.store = SqliteSessionStore(db)
        self._run_store = SqliteRunStore(db)

    def save_completed(
        self,
        agent_input: AgentInput,
        output: AgentOutput,
        effective_agent_name: str,
        run_id: str,
        usage: Optional[ModelUsage] = None,
        session_type: str = "coding",
    ) -> AgentOutput:
        """当智能体顺利完成工作时调用！把这次对话的快照、详细执行轨迹（Trace）全部保存，
        并且把这次运行的状态更新为“已完成（completed）”。

        需要拿到的东西：
        - agent_input: 用户传过来的输入参数（如会话 ID 等）。
        - output: 智能体运行出来的最终输出结果（含回复和事件）。
        - effective_agent_name: 这次实际干活的智能体名字。
        - run_id: 这次运行的唯一 ID。
        - usage: 大模型消耗的 Token 统计信息（可选）。
        - session_type: 会话类型（默认 "coding"）。

        会给出来的结果：
        - 一个更新了元数据（RunMetadata）之后的 AgentOutput 结果对象。
        """
        metadata = RunMetadata(
            session_id=agent_input.session_id,
            run_id=run_id,
            agent_name=effective_agent_name,
            skill_name=agent_input.skill_name,
        )
        output = output.model_copy(update={"metadata": metadata})
        try:
            self.store.upsert_session_snapshot(
                agent_input.session_id,
                state=output.state,
                last_agent_name=effective_agent_name,
                last_skill_name=agent_input.skill_name,
                last_reply_preview=build_reply_preview(output.reply),
                context_tokens=usage.input_tokens if usage else None,
                session_type=session_type,
            )
            self._run_store.save_run_trace(
                session_id=agent_input.session_id,
                run_id=run_id,
                agent_name=effective_agent_name,
                skill_name=agent_input.skill_name,
                user_input=agent_input.user_input,
                reply=output.reply,
                events=output.events,
            )
            self.db.flush()
            self._run_store.update_run_status(run_id=run_id, status="completed")
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return output

    def save_cancelled(
        self,
        session_id: str,
        run_id: str,
        user_input: str,
        partial_reply: str,
        agent_name: Optional[str],
        skill_name: Optional[str],
        events: Optional[list] = None,
    ) -> dict:
        """当智能体运行被打断或取消时调用！作为一个兜底保护，它要把目前已经产生的半成品回复、
        当前最新的聊天状态和事件都给存下来，不让用户的聊天记录丢失，并且把这次运行的状态标记为“已取消（cancelled）”。

        需要拿到的东西：
        - session_id: 会话的唯一 ID。
        - run_id: 运行的唯一 ID。
        - user_input: 用户的这轮输入。
        - partial_reply: 智能体中途被打断时已经吐出来的半成品回复。
        - agent_name: 智能体名字。
        - skill_name: 使用的技能名字。
        - events: 到目前为止产生的所有事件列表（可选）。

        会给出来的结果：
        - 一个简单的成功标记字典，如 `{"ok": True}`。
        """
        state = self.store.get(session_id) or AgentState()
        # 用户消息在运行时只存在于内存 agent.state 里，stop 时尚未落库。
        # 若当前 state 最后一条不是本轮的 user 消息，则补入，避免刷新后对话消失。
        if user_input and (
            not state.messages
            or state.messages[-1].role != "user"
            or state.messages[-1].content != user_input
        ):
            state.messages.append(ChatMessage(role="user", content=user_input))
        try:
            self._run_store.save_partial_run(
                session_id=session_id,
                run_id=run_id,
                agent_name=agent_name,
                skill_name=skill_name,
                user_input=user_input,
                partial_reply=partial_reply,
                state=state,
                events=events or [],
            )
            self._run_store.update_run_status(run_id=run_id, status="cancelled")
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"ok": True}

    def save_resumed(
        self,
        run_id: str,
        session_id: str,
        events: list,
        partial_reply: str,
        agent_state,
    ) -> None:
        """当人工审批通过，智能体恢复运行并且彻底把后面的工作做完时调用！
        它会把新产生的事件追加到记录里，同步保存最新的会话状态快照，最后把状态改成“已完成（completed）”。

        需要拿到的东西：
        - run_id: 运行的唯一 ID.
        - session_id: 会话的唯一 ID.
        - events: 恢复后新产生的事件列表。
        - partial_reply: 恢复运行后的最终回复。
        - agent_state: 最新的完整智能体状态快照。
        """
        try:
            self._run_store.append_run_events(
                run_id=run_id,
                new_events=events,
                final_reply=partial_reply,
            )
            self._run_store.update_run_status(run_id=run_id, status="completed")
            self.store.upsert_session_snapshot(
                session_id=session_id,
                state=agent_state,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def get_run_detail(self, session_id: str, run_id: str):
        """查账！去数据库里查询某一次具体运行的详情（比如智能体的回答和调用过的工具），
        并且会仔细核对这个运行是不是真的属于当前这个会话，防止查错。

        需要拿到的东西：
        - session_id: 会话 ID。
        - run_id: 运行 ID。

        会给出来的结果：
        - 一个元组：(RunRecord 运行记录对象, ToolCallRecords 工具调用记录列表)。如果找不到或者对不上，就返回 `None, []`。
        """
        run, tool_calls = self._run_store.get_run_detail(run_id)
        if not run or run.session_id != session_id:
            return None, []
        return run, tool_calls

    def save_resumed_partial(
        self,
        *,
        run_id: str,
        session_id: str,
        events: list,
        agent_state,
    ) -> None:
        """审批恢复后只完成了当前一个工具，但同 run 仍有其它 pending approval。

        这时要：
        1. 追加当前工具产生的事件
        2. 更新 session snapshot
        3. 保持 run_status = paused
        """
        try:
            self._run_store.append_run_events_partial(
                run_id=run_id,
                new_events=events,
            )
            self.store.upsert_session_snapshot(
                session_id=session_id,
                state=agent_state,
            )
            self._run_store.update_run_status(run_id=run_id, status="paused")
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
