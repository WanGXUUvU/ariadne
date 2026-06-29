import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.agent import AgentDefinition
from backend.core.types import ChatMessage
from backend.run.types import RunFinalStatus
from backend.run.execute_run_resume import execute_run_resume
from backend.agent_loop.types import RunState
from backend.approval.store import SqliteApprovalStore
from backend.infra.db.orm_models import SessionRunRecord
from backend.session.store import SessionStore
from backend.tests.helpers.db import make_sqlite_test_db


def _parse_sse(frame: str) -> dict:
    assert frame.startswith("data: ")
    return json.loads(frame[len("data: ") :].strip())


def _seed_session(db, session_id: str, workspace_path: Path) -> None:
    SessionStore(db).save_state(
        session_id=session_id,
        state=RunState(),
        workspace_path=str(workspace_path),
    )


def _seed_run(db, session_id: str, run_id: str) -> None:
    db.add(
        SessionRunRecord(
            session_id=session_id,
            run_id=run_id,
            run_status="paused",
            agent_name="default",
            user_input="需要审批",
            reply="",
            event_count=0,
        )
    )


class TestResumeRun(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.engine, self.session_local = make_sqlite_test_db(
            self.temp_dir.name,
            "test_resume_run_service.db",
        )

    def tearDown(self):
        self.engine.dispose()
        self.temp_dir.cleanup()

    async def test_resume_run_paused_path_uses_finalization_input(self):
        db = self.session_local()
        try:
            session_id = "resume-paused-session"
            run_id = "resume-paused-run"
            _seed_session(db, session_id, self.workspace)
            _seed_run(db, session_id, run_id)

            approval_store = SqliteApprovalStore(db)
            approval = approval_store.create(
                session_id=session_id,
                run_id=run_id,
                batch_id=run_id,
                tool_name="write_file",
                tool_call_id="call_001",
                arguments='{"path":"a.txt","content":"x"}',
                saved_messages=[ChatMessage(role="user", content="需要审批")],
                event_index=0,
            )
            db.commit()

            recorder = MagicMock()

            with (
                patch(
                    "backend.run.execute_run_resume.load_agent_definition",
                    return_value=AgentDefinition(
                        id="default",
                        name="Default",
                        system_prompt="test",
                        description="test",
                        tool_names=[],
                    ),
                ) as load_definition,
                patch(
                    "backend.run.execute_run_resume.build_model_adapter",
                    side_effect=AssertionError(
                        "paused resume path should not build model adapter"
                    ),
                ),
            ):
                frames = []
                async for frame in execute_run_resume(
                    db=db,
                    approval_id=approval.id,
                    rejected=True,
                    recorder=recorder,
                    approval_store=approval_store,
                    session_store=SessionStore(db),
                ):
                    frames.append(_parse_sse(frame))

            load_definition.assert_called_once()
            self.assertEqual(load_definition.call_args.kwargs["agent_id"], "default")
            self.assertEqual(frames[-1]["type"], "paused")
            self.assertEqual(recorder.finalize_run.call_count, 1)
            finalization = recorder.finalize_run.call_args.kwargs["finalization"]
            self.assertEqual(finalization.status, RunFinalStatus.PAUSED)
            self.assertTrue(finalization.is_resume)
            self.assertEqual(finalization.run_id, run_id)
            self.assertEqual(finalization.state.messages[-1].role, "tool")
            self.assertEqual(finalization.state.messages[-1].tool_call_id, "call_001")
            self.assertIn("[TOOL_REJECTED]", finalization.state.messages[-1].content)
        finally:
            db.close()

    async def test_resume_run_completed_path_uses_finalization_input(self):
        db = self.session_local()
        try:
            session_id = "resume-completed-session"
            run_id = "resume-completed-run"
            _seed_session(db, session_id, self.workspace)
            _seed_run(db, session_id, run_id)

            approval_store = SqliteApprovalStore(db)
            approval = approval_store.create(
                session_id=session_id,
                run_id=run_id,
                batch_id=run_id,
                tool_name="write_file",
                tool_call_id="call_002",
                arguments='{"path":"b.txt","content":"y"}',
                saved_messages=[ChatMessage(role="user", content="继续执行")],
                event_index=0,
            )
            db.commit()

            async def fake_stream(self, *args, **kwargs):
                yield "done"

            class FakeRunner:
                def __init__(self):
                    self.state = RunState()
                    self.last_usage = None

                stream = fake_stream

            recorder = MagicMock()

            with (
                patch(
                    "backend.run.execute_run_resume.load_agent_definition",
                    return_value=AgentDefinition(
                        id="default",
                        name="Default",
                        system_prompt="test",
                        description="test",
                        tool_names=[],
                    ),
                ) as load_definition,
                patch(
                    "backend.run.execute_run_resume.build_model_adapter",
                    return_value=object(),
                ),
                patch.object(
                    approval_store,
                    "is_batch_fully_resolved",
                    return_value=True,
                ),
                patch(
                    "backend.run.execute_run_resume.build_agent_loop",
                    return_value=FakeRunner(),
                ),
            ):
                frames = []
                async for frame in execute_run_resume(
                    db=db,
                    approval_id=approval.id,
                    rejected=True,
                    recorder=recorder,
                    approval_store=approval_store,
                    session_store=SessionStore(db),
                ):
                    frames.append(_parse_sse(frame))

            load_definition.assert_called_once()
            self.assertEqual(load_definition.call_args.kwargs["agent_id"], "default")
            self.assertEqual(frames[-1]["type"], "end")
            self.assertEqual(recorder.finalize_run.call_count, 1)
            finalization = recorder.finalize_run.call_args.kwargs["finalization"]
            self.assertEqual(finalization.status, RunFinalStatus.COMPLETED)
            self.assertTrue(finalization.is_resume)
            self.assertEqual(finalization.reply, "done")
            self.assertEqual(finalization.run_id, run_id)

            persisted_state = SessionStore(db).read_session_state(session_id)
            self.assertEqual(persisted_state.messages[-1].role, "tool")
            self.assertEqual(persisted_state.messages[-1].tool_call_id, "call_002")
            self.assertIn("[TOOL_REJECTED]", persisted_state.messages[-1].content)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
