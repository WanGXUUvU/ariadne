import tempfile
import unittest

from agent_prototype.agent.definition import AgentDefinitionService
from agent_prototype.agent.types import AgentDefinition
from agent_prototype.agent.definition import SqliteAgentDefinitionStore
from agent_prototype.tests.helpers.db import make_sqlite_test_db


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

            # 实例化全新的 OOP Service 并测试
            service = AgentDefinitionService(db)
            definition = service.load_definition("default")

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
            service = AgentDefinitionService(db)
            definition = service.load_definition("default")

            self.assertEqual(definition.id, "default")
            self.assertEqual(definition.name, "Default Agent")
            self.assertEqual(definition.system_prompt, "你是一个助手。")
            self.assertEqual(definition.description, "通用助理，不限制工具，适合各类任务")
            self.assertIsNone(definition.tool_names)
        finally:
            db.close()

    def test_load_unknown_agent_definition_raises(self):
        db = self.session_local()
        try:
            service = AgentDefinitionService(db)
            with self.assertRaises(ValueError) as ctx:
                service.load_definition("reviewer")
        finally:
            db.close()

        self.assertIn("Unknown agent definition", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
