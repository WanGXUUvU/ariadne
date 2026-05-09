import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agent_prototype.application.agent_definition_service import load_agent_definition
from agent_prototype.core.agent_definition import AgentDefinition
from agent_prototype.storage.db import Base
from agent_prototype.storage.stores.agent_definition_store import SqliteAgentDefinitionStore


class TestAgentLoader(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "test_loader.db"
        self.engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)
        self.session_local = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def tearDown(self):
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_load_default_agent_definition_from_database(self):
        db = self.session_local()
        try:
            store = SqliteAgentDefinitionStore(db)
            store.save(
                AgentDefinition(
                    id="default",
                    name="Default Agent",
                    system_prompt="数据库里的提示词",
                    description="from db",
                    tool_names=["echo_tool"],
                )
            )

            definition = load_agent_definition("default", db)

            self.assertEqual(definition.id, "default")
            self.assertEqual(definition.name, "Default Agent")
            self.assertEqual(definition.system_prompt, "数据库里的提示词")
            self.assertEqual(definition.description, "from db")
            self.assertEqual(definition.tool_names, ["echo_tool"])
        finally:
            db.close()

    def test_load_default_agent_definition_falls_back_to_memory_default(self):
        db = self.session_local()
        try:
            definition = load_agent_definition("default", db)

            self.assertEqual(definition.id, "default")
            self.assertEqual(definition.name, "Default Agent")
            self.assertEqual(definition.system_prompt, "你是一个助手")
            self.assertIsNone(definition.description)
            self.assertIsNone(definition.tool_names)
        finally:
            db.close()

    def test_load_unknown_agent_definition_raises(self):
        db = self.session_local()
        try:
            with self.assertRaises(ValueError) as ctx:
                load_agent_definition("reviewer", db)
        finally:
            db.close()

        self.assertIn("Unknown agent definition", str(ctx.exception))
