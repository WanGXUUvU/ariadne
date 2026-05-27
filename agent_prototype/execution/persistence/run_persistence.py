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
from agent_prototype.model.types.model_types import ModelUsage
from agent_prototype.api.dto.schemas import AgentInput, AgentOutput, AgentState, ChatMessage, RunMetadata
from agent_prototype.execution.streaming.sse import build_reply_preview


class RunPersistenceService:
    """负责把 run 的结果写进数据库。"""

    def __init__(self, db: Session):
        self.db = db
        self.store = SqliteSessionStore(db)

    def save_completed(
        self,
        agent_input: AgentInput,
        output: AgentOutput,
        effective_agent_name: str,
        run_id: str,
        usage: Optional[ModelUsage] = None,
        session_type: str = "coding",
    ) -> AgentOutput:
        """正常完成时：存快照、存 trace、刷状态为 completed。"""
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
            self.store.save_run_trace(
                session_id=agent_input.session_id,
                run_id=run_id,
                agent_name=effective_agent_name,
                skill_name=agent_input.skill_name,
                user_input=agent_input.user_input,
                reply=output.reply,
                events=output.events,
            )
            self.db.flush()
            self.store.update_run_status(run_id=run_id, status="completed")
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
        """意外中断时兜底：存 partial run，状态标记为 cancelled。"""
        state = self.store.get(session_id) or AgentState()
        # 用户消息在运行时只存在于内存 agent.state 里，stop 时尚未落库。
        # 若当前 state 最后一条不是本轮的 user 消息，则补入，避免刷新后对话消失。
        if user_input and (not state.messages or state.messages[-1].role != "user" or state.messages[-1].content != user_input):
            state.messages.append(ChatMessage(role="user", content=user_input))
        try:
            self.store.save_partial_run(
                session_id=session_id,
                run_id=run_id,
                agent_name=agent_name,
                skill_name=skill_name,
                user_input=user_input,
                partial_reply=partial_reply,
                state=state,
                events=events or [],
            )
            self.store.update_run_status(run_id=run_id, status="cancelled")
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
        """审批恢复完成时：追加事件、同步 session 快照、刷新状态为 completed。"""
        try:
            self.store.append_run_events(
                run_id=run_id,
                new_events=events,
                final_reply=partial_reply,
            )
            self.store.update_run_status(run_id=run_id, status="completed")
            self.store.upsert_session_snapshot(
                session_id=session_id,
                state=agent_state,
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def get_run_detail(self, session_id: str, run_id: str):
        """查询 run 详情，校验 session 归属。"""
        run, tool_calls = self.store.get_run_detail(run_id)
        if not run or run.session_id != session_id:
            return None, []
        return run, tool_calls