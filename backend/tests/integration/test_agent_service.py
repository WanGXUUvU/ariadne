import tempfile
import unittest

from backend.agent import (
    AgentDefinition,
    load_agent_definition,
    SqliteAgentDefinitionStore,
)
from backend.tests.helpers.db import make_sqlite_test_db


class TestAgentLoader(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.engine, self.session_local = make_sqlite_test_db(
            self.temp_dir.name,
            "test_loader.db",
        )

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
            db.commit()

            definition = load_agent_definition(
                db=db,
                agent_id="default",
            )

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
            definition = load_agent_definition(
                db=db,
                agent_id="default",
            )

            self.assertEqual(definition.id, "default")
            self.assertEqual(definition.name, "Default Agent")
            self.assertEqual(definition.system_prompt, "")
            self.assertEqual(
                definition.description, "通用助理，不限制工具，适合各类任务"
            )
            self.assertIsNone(definition.tool_names)
        finally:
            db.close()

    def test_load_unknown_agent_definition_raises(self):
        db = self.session_local()
        try:
            with self.assertRaises(ValueError) as ctx:
                load_agent_definition(
                    db=db,
                    agent_id="reviewer",
                )
        finally:
            db.close()

        self.assertIn("Unknown agent definition", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
