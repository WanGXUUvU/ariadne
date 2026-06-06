import asyncio
import gc
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agent_prototype.core.types import ModelStreamEvent, ToolCall, ToolCallFunction
from agent_prototype.execution.persistence.types import AgentInput
from agent_prototype.execution.runtime.types import AgentState
from agent_prototype.execution.runtime.vfs import RunVfsRegistry
from agent_prototype.execution.service import RunService
from agent_prototype.execution.runtime_context_factory import RuntimeContextFactory
from agent_prototype.infra.db.orm_models import SessionRunRecord, ToolCallRecord
from agent_prototype.memory.session.store import SqliteSessionStore
from agent_prototype.tests.helpers.db import make_sqlite_test_db
from agent_prototype.tests.helpers.factories import build_assistant_response


def _seed_session(session_local, session_id: str, workspace_path: Path) -> None:
    db = session_local()
    try:
        store = SqliteSessionStore(db)
        record = store.upsert_session_snapshot(
            session_id,
            state=AgentState(),
            workspace_path=str(workspace_path),
            session_type="coding",
        )
        record.permission_profile = "full-auto"
        db.commit()
    finally:
        db.close()


def _parse_sse(frame: str) -> dict:
    assert frame.startswith("data: ")
    return json.loads(frame[len("data: ") :].strip())


class FakeSyncAdapter:
    def __init__(self, responses):
        self.responses = list(responses)

    def generate(self, request):
        return self.responses.pop(0)


class FakeAsyncAdapter:
    def __init__(self, tool_path: str, content: str):
        self.tool_path = tool_path
        self.content = content
        self.call_count = 0
        self.blocker = asyncio.Event()

    async def async_stream_generate(self, request):
        self.call_count += 1
        if self.call_count == 1:
            yield ModelStreamEvent(
                type="tool_call_delta",
                finish_reason="tool_calls",
                raw_event={
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "call_write_001",
                            "function": {
                                "name": "write_file",
                                "arguments": json.dumps(
                                    {
                                        "path": self.tool_path,
                                        "content": self.content,
                                    }
                                ),
                            },
                        }
                    ]
                },
            )
            return

        yield ModelStreamEvent(type="delta", content_delta="partial")
        await self.blocker.wait()


class TestVfsAcceptance(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temp_dir.name) / "workspace"
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.engine, self.session_local = make_sqlite_test_db(
            self.temp_dir.name,
            "test_vfs_acceptance.db",
        )

    def tearDown(self):
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_sync_run_commits_staged_write_to_disk(self):
        session_id = "sync-vfs-session"
        target = self.workspace / "sync.txt"
        _seed_session(self.session_local, session_id, self.workspace)

        adapter = FakeSyncAdapter(
            [
                build_assistant_response(
                    tool_calls=[
                        ToolCall(
                            id="call_sync_write",
                            function=ToolCallFunction(
                                name="write_file",
                                arguments=json.dumps(
                                    {
                                        "path": "sync.txt",
                                        "content": "sync committed content",
                                    }
                                ),
                            ),
                        )
                    ]
                ),
                build_assistant_response(content="done"),
            ]
        )

        with patch.object(RuntimeContextFactory, "_build_adapter", return_value=adapter):
            db = self.session_local()
            try:
                output = RunService(db).run_agent(
                    AgentInput(
                        session_id=session_id,
                        user_input="写一个文件",
                        workspace_path=str(self.workspace),
                    )
                )
            finally:
                db.close()

        self.assertEqual(output.reply, "done")
        self.assertTrue(target.exists())
        self.assertEqual(target.read_text(encoding="utf-8"), "sync committed content")
        self.assertIsNone(RunVfsRegistry.get(output.metadata.run_id))

        db = self.session_local()
        try:
            run = (
                db.query(SessionRunRecord)
                .filter(SessionRunRecord.run_id == output.metadata.run_id)
                .first()
            )
            self.assertIsNotNone(run)
            self.assertEqual(run.run_status, "completed")
        finally:
            db.close()

    async def test_stream_cancel_discards_staged_write_and_persists_cancelled_run(self):
        session_id = "stream-cancel-vfs-session"
        target = self.workspace / "cancelled.txt"
        _seed_session(self.session_local, session_id, self.workspace)

        adapter = FakeAsyncAdapter("cancelled.txt", "staged then discarded")

        with (
            patch.object(RuntimeContextFactory, "_build_adapter", return_value=adapter),
            patch("agent_prototype.execution.streaming.stream_run_session.logger.exception"),
        ):
            db = self.session_local()
            try:
                stream = RunService(db).async_stream_agent(
                    AgentInput(
                        session_id=session_id,
                        user_input="流式写文件然后取消",
                        workspace_path=str(self.workspace),
                    )
                )

                start_frame = _parse_sse(await stream.__anext__())
                run_id = start_frame["data"]["run_id"]
                saw_tool_result = False
                saw_delta = False

                for _ in range(8):
                    frame = _parse_sse(await stream.__anext__())
                    if frame["type"] == "agent_event" and frame["data"]["type"] == "tool_result":
                        saw_tool_result = True
                    if frame["type"] == "delta":
                        saw_delta = True
                        break

                self.assertTrue(saw_tool_result)
                self.assertTrue(saw_delta)
                self.assertFalse(target.exists())

                RunService(db).finalize_run(
                    session_id=session_id,
                    run_id=run_id,
                    user_input="流式写文件然后取消",
                    partial_reply="partial",
                    agent_name="software_engineer",
                    skill_name=None,
                )
                stream = None
                gc.collect()
                await asyncio.sleep(0)
            finally:
                db.close()

        self.assertFalse(target.exists())
        self.assertIsNone(RunVfsRegistry.get(run_id))

        db = self.session_local()
        try:
            run = db.query(SessionRunRecord).filter(SessionRunRecord.run_id == run_id).first()
            self.assertIsNotNone(run)
            self.assertEqual(run.run_status, "cancelled")
            self.assertEqual(run.reply, "partial")

            tool_calls = (
                db.query(ToolCallRecord).filter(ToolCallRecord.run_id == run_id).all()
            )
            self.assertEqual(len(tool_calls), 1)
            self.assertEqual(tool_calls[0].status, "completed")
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
