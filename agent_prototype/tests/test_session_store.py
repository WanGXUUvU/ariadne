import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agent_prototype.interface.dto.schemas import AgentState
from agent_prototype.infrastructure.database.db import Base
from agent_prototype.infrastructure.database.repositories.session_store import SqliteSessionStore


class TestSessionStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "test_session_store.db"
        self.engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)
        self.session_local = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_upsert_session_snapshot_keeps_existing_nullable_metadata_when_not_provided(self):
        db = self.session_local()
        try:
            store = SqliteSessionStore(db)
            store.upsert_session_snapshot(
                "session-keep-metadata",
                state=AgentState(messages=[{"role": "user", "content": "你好"}]),
                last_agent_name="default",
                last_skill_name="openai-docs",
                last_reply_preview="上一次回复摘要",
            )
            db.commit()

            store.upsert_session_snapshot(
                "session-keep-metadata",
                state=AgentState(messages=[{"role": "user", "content": "新的消息"}]),
            )
            db.commit()

            record = store.read_session_record("session-keep-metadata")
            self.assertIsNotNone(record)
            self.assertEqual(record.last_agent_name, "default")
            self.assertEqual(record.last_skill_name, "openai-docs")
            self.assertEqual(record.last_reply_preview, "上一次回复摘要")
        finally:
            db.close()

    def test_upsert_session_snapshot_allows_explicit_none_to_clear_nullable_metadata(self):
        db = self.session_local()
        try:
            store = SqliteSessionStore(db)
            store.upsert_session_snapshot(
                "session-clear-metadata",
                state=AgentState(messages=[{"role": "user", "content": "你好"}]),
                last_agent_name="default",
                last_skill_name="openai-docs",
                last_reply_preview="上一次回复摘要",
            )
            db.commit()

            store.upsert_session_snapshot(
                "session-clear-metadata",
                state=AgentState(),
                last_agent_name=None,
                last_skill_name=None,
                last_reply_preview=None,
            )
            db.commit()

            record = store.read_session_record("session-clear-metadata")
            self.assertIsNotNone(record)
            self.assertIsNone(record.last_agent_name)
            self.assertIsNone(record.last_skill_name)
            self.assertIsNone(record.last_reply_preview)
        finally:
            db.close()
