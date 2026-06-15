import tempfile
import unittest

from agent_prototype.core.types import ChatMessage
from agent_prototype.infra.db.orm_models import SessionRunRecord
from agent_prototype.security.approval.service import ApprovalRunNotPaused, ApprovalService
from agent_prototype.security.approval.store import SqliteApprovalStore
from agent_prototype.tests.helpers.db import make_sqlite_test_db


class TestApprovalService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.engine, self.session_local = make_sqlite_test_db(
            self.temp_dir.name,
            "test_approval_service.db",
        )

    def tearDown(self):
        self.engine.dispose()
        self.temp_dir.cleanup()

    def _seed_approval(self, db, run_status: str):
        session_id = "approval-session"
        run_id = "approval-run"
        db.add(
            SessionRunRecord(
                session_id=session_id,
                run_id=run_id,
                run_status=run_status,
                agent_name="default",
                user_input="needs approval",
                reply="",
                event_count=0,
            )
        )
        approval = SqliteApprovalStore(db).create(
            session_id=session_id,
            run_id=run_id,
            batch_id=run_id,
            tool_name="write_file",
            tool_call_id="call_001",
            arguments="{}",
            saved_messages=[ChatMessage(role="user", content="needs approval")],
            event_index=0,
        )
        db.commit()
        return approval

    def test_approve_rejects_run_that_is_not_paused(self):
        db = self.session_local()
        try:
            approval = self._seed_approval(db, "running")

            with self.assertRaises(ApprovalRunNotPaused):
                ApprovalService(db).approve(approval.id)

            db.refresh(approval)
            self.assertEqual(approval.status, "pending")
        finally:
            db.close()

    def test_approve_succeeds_after_run_is_paused(self):
        db = self.session_local()
        try:
            approval = self._seed_approval(db, "paused")

            record = ApprovalService(db).approve(approval.id)

            self.assertIsNotNone(record)
            self.assertEqual(record.status, "approved")
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
