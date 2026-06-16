import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.agent.types import AgentDefinition
from backend.core.types import ChatMessage
from backend.execution.persistence.types import RunFinalStatus
from backend.execution.resume.service import ResumeRunService
from backend.execution.runtime.types import RunState
from backend.infra.db.orm_models import SessionRunRecord
from backend.memory.session.store import SessionStore
from backend.security.approval.store import SqliteApprovalStore
from backend.tests.helpers.db import make_sqlite_test_db


def _parse_sse(frame: str) -> dict:
    assert frame.startswith("data: ")
    return json.loads(frame[len("data: ") :].strip())


def _seed_session(db, session_id: str, workspace_path: Path) -> None:
    SessionStore(db).save_state(
        session_id=session_id,
        state=RunState(),
        workspace_path=str(workspace_path),
        session_type="coding",
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


class TestResumeRunService(unittest.IsolatedAsyncioTestCase):
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

            service = ResumeRunService(db)
            service.recorder.finalize_run = MagicMock()

            with (
                patch(
                    "backend.execution.resume.service.AgentDefinitionService.load_definition",
                    return_value=AgentDefinition(
                        id="default",
                        name="Default",
                        system_prompt="test",
                        description="test",
                        tool_names=[],
                    ),
                ) as load_definition,
                patch(
                    "backend.execution.resume.service.RunContextFactory.create_adapter",
                    return_value=object(),
                ),
            ):
                frames = []
                async for frame in service.resume_run(approval.id, rejected=True):
                    frames.append(_parse_sse(frame))

            load_definition.assert_called_once_with("default")
            self.assertEqual(frames[-1]["type"], "paused")
            self.assertEqual(service.recorder.finalize_run.call_count, 1)
            finalization = service.recorder.finalize_run.call_args.args[0]
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

            async def fake_async_stream_run(self, *args, **kwargs):
                yield "done"

            service = ResumeRunService(db)
            service.recorder.finalize_run = MagicMock()

            with (
                patch(
                    "backend.execution.resume.service.AgentDefinitionService.load_definition",
                    return_value=AgentDefinition(
                        id="default",
                        name="Default",
                        system_prompt="test",
                        description="test",
                        tool_names=[],
                    ),
                ) as load_definition,
                patch(
                    "backend.execution.resume.service.RunContextFactory.create_adapter",
                    return_value=object(),
                ),
                patch.object(
                    service.approval_store,
                    "is_batch_fully_resolved",
                    return_value=True,
                ),
                patch(
                    "backend.execution.resume.service.AgentRunner.async_stream_run",
                    new=fake_async_stream_run,
                ),
            ):
                frames = []
                async for frame in service.resume_run(approval.id, rejected=True):
                    frames.append(_parse_sse(frame))

            load_definition.assert_called_once_with("default")
            self.assertEqual(frames[-1]["type"], "end")
            self.assertEqual(service.recorder.finalize_run.call_count, 1)
            finalization = service.recorder.finalize_run.call_args.args[0]
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
