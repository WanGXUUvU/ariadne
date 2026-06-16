from sqlalchemy.orm import Session

from agent_prototype.core.types import ChatMessage
from agent_prototype.execution.persistence.types import (
    RunFinalizationInput,
    RunFinalStatus,
)
from agent_prototype.execution.runtime.types import RunState
from agent_prototype.execution.runtime.vfs import RunVfsRegistry
from agent_prototype.execution.streaming.sse import build_reply_preview
from agent_prototype.memory.run.store import RunTraceStore
from agent_prototype.memory.session.store import SessionStore
from agent_prototype.security.approval.store import SqliteApprovalStore
from agent_prototype.tools.result_types import ToolState


class RunRecorder:
    """run 终态统一持久化入口。"""

    def __init__(self, db: Session):
        self.db = db
        self.store = SessionStore(db)
        self._run_store = RunTraceStore(db)
        self.approval_store = SqliteApprovalStore(db)

    def finalize_run(self, finalization: RunFinalizationInput) -> None:
        """统一收口一次 run 的终态，并根据终态执行 DB/VFS 动作。"""
        try:
            if finalization.status == RunFinalStatus.COMPLETED:
                self._finalize_completed(finalization)
            elif finalization.status == RunFinalStatus.PAUSED:
                self._finalize_paused(finalization)
            elif finalization.status == RunFinalStatus.CANCELLED:
                self._finalize_interrupted(finalization, RunFinalStatus.CANCELLED)
            elif finalization.status == RunFinalStatus.FAILED:
                self._finalize_interrupted(finalization, RunFinalStatus.FAILED)

            self.db.commit()
            self._apply_vfs_terminal_action(finalization)
        except Exception:
            self.db.rollback()
            raise

    def _finalize_completed(self, finalization: RunFinalizationInput) -> None:
        for event in finalization.events:
            if (
                event.tool_result
                and event.tool_result.metadata.get("state") == "staged"
            ):
                event.tool_result.metadata["state"] = ToolState.COMMITTED.value
        if finalization.is_resume:
            if finalization.owns_session:
                self.store.save_state(
                    session_id=finalization.session_id,
                    state=finalization.state,
                    last_agent_name=finalization.agent_name,
                    last_reply_preview=build_reply_preview(finalization.reply),
                )
            self._run_store.append_run_events(
                run_id=finalization.run_id,
                new_events=finalization.events,
                final_reply=finalization.reply,
            )
            self._run_store.update_run_status(
                run_id=finalization.run_id,
                status=RunFinalStatus.COMPLETED.value,
            )
            return
        if finalization.is_resume is False:
            if finalization.owns_session:
                self.store.save_state(
                    finalization.session_id,
                    state=finalization.state,
                    last_agent_name=finalization.agent_name,
                    last_reply_preview=build_reply_preview(finalization.reply),
                    context_tokens=(
                        finalization.usage.input_tokens if finalization.usage else None
                    ),
                )
            self._run_store.save_run_trace(
                session_id=finalization.session_id,
                run_id=finalization.run_id,
                agent_name=finalization.agent_name,
                user_input=finalization.user_input,
                reply=finalization.reply,
                events=finalization.events,
            )
            self.db.flush()
            self._run_store.update_run_status(
                run_id=finalization.run_id,
                status=RunFinalStatus.COMPLETED.value,
            )

    def _finalize_paused(self, finalization: RunFinalizationInput) -> None:
        if finalization.is_resume:
            if finalization.owns_session:
                self.store.save_state(
                    session_id=finalization.session_id,
                    state=finalization.state,
                )
            self._run_store.append_run_events_partial(
                run_id=finalization.run_id,
                new_events=finalization.events,
            )
        else:
            self._run_store.save_partial_run(
                session_id=finalization.session_id,
                run_id=finalization.run_id,
                agent_name=finalization.agent_name,
                user_input=finalization.user_input,
                reply=finalization.reply,
                state=finalization.state,
                events=finalization.events,
            )

        self._run_store.update_run_status(
            run_id=finalization.run_id,
            status=RunFinalStatus.PAUSED.value,
        )

    def _finalize_interrupted(
        self,
        finalization: RunFinalizationInput,
        status: RunFinalStatus,
    ) -> None:
        state = self._ensure_user_message(finalization.state, finalization.user_input)
        for event in finalization.events:
            if (
                event.tool_result
                and event.tool_result.metadata.get("state") == "staged"
            ):
                event.tool_result.metadata["state"] = ToolState.ROLLED_BACK.value
        if finalization.is_resume:
            if finalization.owns_session:
                self.store.save_state(
                    session_id=finalization.session_id,
                    state=state,
                )
            self._run_store.append_run_events_partial(
                run_id=finalization.run_id,
                new_events=finalization.events,
            )
        else:
            self._run_store.save_partial_run(
                session_id=finalization.session_id,
                run_id=finalization.run_id,
                agent_name=finalization.agent_name,
                user_input=finalization.user_input,
                reply=finalization.reply,
                state=state,
                events=finalization.events,
            )

        self._run_store.update_run_status(
            run_id=finalization.run_id,
            status=status.value,
        )

    def _apply_vfs_terminal_action(self, finalization: RunFinalizationInput) -> None:
        if finalization.status == RunFinalStatus.COMPLETED:
            staged_vfs = RunVfsRegistry.get(finalization.run_id)
            if staged_vfs is not None:
                staged_vfs.commit_all()
                RunVfsRegistry.take(finalization.run_id)
            return

        if finalization.status in (RunFinalStatus.CANCELLED, RunFinalStatus.FAILED):
            RunVfsRegistry.discard(finalization.run_id)

    def _ensure_user_message(self, state: RunState, user_input: str) -> RunState:
        if user_input and (
            not state.messages
            or state.messages[-1].role != "user"
            or state.messages[-1].content != user_input
        ):
            state.messages.append(ChatMessage(role="user", content=user_input))
        return state
