import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agent_prototype.runtime.agent import Agent
from agent_prototype.core.agent_definition import AgentDefinition
from agent_prototype.storage.agent_definition_store import SqliteAgentDefinitionStore
from agent_prototype.api.app import app
from agent_prototype.runtime.agent_loader import load_agent_definition
from agent_prototype.runtime.tool_registry import build_default_tool_registry
from agent_prototype.storage.db import Base, get_db
from agent_prototype.storage.models import SessionRecord
from agent_prototype.core.schemas import AgentInput


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
            self.assertEqual(definition.description, None)
            self.assertEqual(definition.tool_names, None)
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


class TestAgent(unittest.TestCase):
    @patch("agent_prototype.runtime.agent.call_llm", return_value={"role": "assistant", "content": "mock reply"})
    def test_run_uses_definition_system_prompt(self, mock_call_llm):
        custom_definition = AgentDefinition(
            id="default",
            name="Default Agent",
            system_prompt="你是一个严格的代码审查助手",
            description="test definition",
            tool_names=[],
        )

        agent = Agent(definition=custom_definition)
        agent_input = AgentInput(session_id="session-a", user_input="你好")

        output = agent.run(agent_input)

        self.assertEqual(output.reply, "mock reply")
        messages = mock_call_llm.call_args.args[0]
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[0]["content"], "你是一个严格的代码审查助手")
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(messages[1]["content"], "你好")

    @patch("agent_prototype.runtime.agent.call_llm", return_value={"role": "assistant", "content": "mock reply"})
    def test_run_updates_state_and_returns_reply(self, mock_call_llm):
        agent = Agent()
        agent_input = AgentInput(session_id="session-a", user_input="你好")

        output = agent.run(agent_input)

        self.assertEqual(output.reply, "mock reply")
        self.assertEqual(output.state.step, 1)
        self.assertEqual(
            [m.model_dump(exclude_none=True) for m in output.state.messages],
            [
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "mock reply"},
            ],
        )
        self.assertEqual(
            [e.model_dump(exclude_none=True) for e in output.events],
            [
                {
                    "index": 0,
                    "type": "final_answer",
                    "content": "mock reply",
                }
            ],
        )
        mock_call_llm.assert_called_once()

    @patch(
        "agent_prototype.runtime.agent.call_llm",
        side_effect=[
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_001",
                        "type": "function",
                        "function": {
                            "name": "echo_tool",
                            "arguments": "{\"text\": \"hello\"}",
                        },
                    }
                ],
            },
            {"role": "assistant", "content": "final reply"},
        ],
    )
    def test_run_handles_tool_call_then_returns_final_reply(self, mock_call_llm):
        agent = Agent()
        agent_input = AgentInput(session_id="session-a", user_input="帮我测试工具")

        output = agent.run(agent_input)

        self.assertEqual(output.reply, "final reply")
        self.assertEqual(output.state.step, 1)
        self.assertEqual(
            [m.model_dump(exclude_none=True) for m in output.state.messages],
            [
                {"role": "user", "content": "帮我测试工具"},
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_001",
                            "type": "function",
                            "function": {
                                "name": "echo_tool",
                                "arguments": "{\"text\": \"hello\"}",
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "content": "tool received:hello",
                    "tool_call_id": "call_001",
                },
                {"role": "assistant", "content": "final reply"},
            ],
        )
        self.assertEqual(
            [e.model_dump(exclude_none=True) for e in output.events],
            [
                {
                    "index": 0,
                    "type": "assistant_tool_call",
                    "tool_name": "echo_tool",
                    "tool_call_id": "call_001",
                    "content": "{\"text\": \"hello\"}",
                },
                {
                    "index": 1,
                    "type": "tool_result",
                    "tool_name": "echo_tool",
                    "tool_call_id": "call_001",
                    "content": "tool received:hello",
                    "tool_result": {
                        "ok": True,
                        "content": "tool received:hello",
                        "metadata": {"tool_name": "echo_tool"},
                    },
                },
                {
                    "index": 2,
                    "type": "final_answer",
                    "content": "final reply",
                },
            ],
        )
        self.assertEqual(mock_call_llm.call_count, 2)

    @patch(
        "agent_prototype.runtime.agent.call_llm",
        side_effect=[
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_001",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": "{\"path\": \"demo.txt\", \"content\": \"hello\"}",
                        },
                    }
                ],
            }
        ],
    )
    def test_run_rejects_disallowed_tool_call(self, mock_call_llm):
        agent = Agent(
            definition=AgentDefinition(
                id="default",
                name="Default Agent",
                system_prompt="你是一个助手",
                description=None,
                tool_names=["echo_tool"],
            )
        )
        agent_input = AgentInput(session_id="session-a", user_input="帮我测试权限")

        with self.assertRaises(ValueError) as ctx:
            agent.run(agent_input)

        self.assertIn("Tool not allowed:write_file", str(ctx.exception))
        self.assertEqual(mock_call_llm.call_count, 1)

    @patch(
        "agent_prototype.runtime.agent.call_llm",
        side_effect=[
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_001",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": "{\"path\": \"/tmp\", \"content\": \"hello\"}",
                        },
                    }
                ],
            },
            {"role": "assistant", "content": "final reply after error"},
        ],
    )
    def test_run_records_tool_error_trace(self, mock_call_llm):
        agent = Agent()
        agent_input = AgentInput(session_id="session-a", user_input="帮我测试错误 trace")

        output = agent.run(agent_input)

        self.assertEqual(output.reply, "final reply after error")
        self.assertEqual(
            [e.model_dump(exclude_none=True) for e in output.events],
            [
                {
                    "index": 0,
                    "type": "assistant_tool_call",
                    "tool_name": "write_file",
                    "tool_call_id": "call_001",
                    "content": "{\"path\": \"/tmp\", \"content\": \"hello\"}",
                },
                {
                    "index": 1,
                    "type": "tool_error",
                    "tool_name": "write_file",
                    "tool_call_id": "call_001",
                    "content": "Path is a directory: /tmp",
                    "tool_result": {
                        "ok": False,
                        "error": {
                            "code": "tool_runtime_error",
                            "tool_name": "write_file",
                            "message": "Path is a directory: /tmp",
                        },
                        "metadata": {"tool_name": "write_file"},
                    },
                },
                {
                    "index": 2,
                    "type": "final_answer",
                    "content": "final reply after error",
                },
            ],
        )
        self.assertEqual(
            [m.model_dump(exclude_none=True) for m in output.state.messages],
            [
                {"role": "user", "content": "帮我测试错误 trace"},
                {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": "call_001",
                            "type": "function",
                            "function": {
                                "name": "write_file",
                                "arguments": "{\"path\": \"/tmp\", \"content\": \"hello\"}",
                            },
                        }
                    ],
                },
                {
                    "role": "tool",
                    "content": "[TOOL_ERROR] Path is a directory: /tmp",
                    "tool_call_id": "call_001",
                },
                {"role": "assistant", "content": "final reply after error"},
            ],
        )
        self.assertEqual(mock_call_llm.call_count, 2)


class TestAgentApi(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "test_agent.db"
        self.engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)

        self.session_local = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        def override_get_db():
            db = self.session_local()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()
        self.temp_dir.cleanup()

    @patch("agent_prototype.runtime.agent.call_llm", return_value={"role": "assistant", "content": "mock reply"})
    def test_run_endpoint(self, mock_call_llm):
        response = self.client.post("/run", json={"session_id": "session-a", "user_input": "你好"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["reply"], "mock reply")
        self.assertEqual(data["state"]["step"], 1)
        self.assertEqual(
            data["state"]["messages"],
            [
                {"role": "user", "content": "你好", "tool_calls": None, "tool_call_id": None},
                {"role": "assistant", "content": "mock reply", "tool_calls": None, "tool_call_id": None},
            ],
        )
        self.assertEqual(
            data["events"],
            [
                {
                    "index": 0,
                    "type": "final_answer",
                    "content": "mock reply",
                    "tool_name": None,
                    "tool_call_id": None,
                    "tool_result": None,
                }
            ],
        )

    @patch("agent_prototype.runtime.agent.call_llm", return_value={"role": "assistant", "content": "mock reply\nwith preview"})
    def test_run_endpoint_updates_session_metadata(self, mock_call_llm):
        response = self.client.post(
            "/run",
            json={"session_id": "session-meta", "user_input": "你好，简单回复我一句"},
        )

        self.assertEqual(response.status_code, 200)

        db = self.session_local()
        try:
            record = db.query(SessionRecord).filter(SessionRecord.session_id == "session-meta").first()

            self.assertIsNotNone(record)
            self.assertEqual(record.session_id, "session-meta")
            self.assertEqual(record.session_name, "session-meta")
            self.assertEqual(record.last_agent_name, "default")
            self.assertIsNone(record.last_skill_name)
            self.assertEqual(record.message_count, 2)
            self.assertEqual(record.last_reply_preview, "mock reply with preview")
            self.assertIsNotNone(record.created_at)
            self.assertIsNotNone(record.updated_at)
            self.assertGreaterEqual(record.updated_at, record.created_at)
        finally:
            db.close()

    @patch("agent_prototype.runtime.services.load_agent_definition")
    @patch("agent_prototype.runtime.agent.call_llm", return_value={"role": "assistant", "content": "review reply"})
    def test_run_endpoint_uses_explicit_agent_name(self, mock_call_llm, mock_load_agent_definition):
        mock_load_agent_definition.return_value = AgentDefinition(
            id="reviewer",
            name="Reviewer Agent",
            system_prompt="你是一个严格的代码审查助手",
            description="review mode",
            tool_names=[],
        )

        response = self.client.post(
            "/run",
            json={"session_id": "session-a", "user_input": "帮我审查", "agent_name": "reviewer"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_load_agent_definition.call_args.args[0], "reviewer")
        self.assertEqual(response.json()["reply"], "review reply")
        self.assertEqual(response.json()["state"]["messages"][0]["role"], "user")
        self.assertEqual(response.json()["state"]["messages"][1]["role"], "assistant")


class TestToolRegistry(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.registry = build_default_tool_registry()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_execute_read_file_tool_call(self):
        file_path = Path(self.temp_dir.name) / "sample.txt"
        file_path.write_text("hello registry", encoding="utf-8")

        result = self.registry.execute_tool_call(
            "read_file",
            f'{{"path":"{file_path}"}}',
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.content, "hello registry")
        self.assertEqual(result.metadata["tool_name"], "read_file")

    def test_execute_list_dir_tool_call(self):
        folder_path = Path(self.temp_dir.name) / "folder"
        folder_path.mkdir()
        (folder_path / "b.txt").write_text("b", encoding="utf-8")
        (folder_path / "a.txt").write_text("a", encoding="utf-8")

        result = self.registry.execute_tool_call(
            "list_dir",
            f'{{"path":"{folder_path}"}}',
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.content, "a.txt\nb.txt")

    def test_execute_search_text_tool_call(self):
        folder_path = Path(self.temp_dir.name) / "search"
        folder_path.mkdir()
        target_file = folder_path / "sample.txt"
        target_file.write_text("hello world\nsearch me here\nbye", encoding="utf-8")

        result = self.registry.execute_tool_call(
            "search_text",
            f'{{"query":"search me","path":"{folder_path}"}}',
        )

        self.assertTrue(result.ok)
        self.assertIn("sample.txt", result.content)
        self.assertIn("search me here", result.content)

    def test_execute_write_file_tool_call(self):
        file_path = Path(self.temp_dir.name) / "written.txt"

        result = self.registry.execute_tool_call(
            "write_file",
            f'{{"path":"{file_path}","content":"hello write"}}',
        )

        self.assertTrue(result.ok)
        self.assertIn("Wrote", result.content)
        self.assertTrue(file_path.exists())
        self.assertEqual(file_path.read_text(encoding="utf-8"), "hello write")

    def test_default_registry_exposes_echo_tool(self):
        schemas = self.registry.get_tool_schemas()
        tool_names = [schema["function"]["name"] for schema in schemas]

        self.assertIn("echo_tool", tool_names)

    def test_unknown_tool_raises_structured_error(self):
        result = self.registry.execute_tool_call("missing_tool", "{}")

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "unknown_tool")
        self.assertEqual(result.error.tool_name, "missing_tool")
        self.assertIn("Unknown tool: missing_tool", result.error.message)

    def test_invalid_json_arguments_raises_structured_error(self):
        result = self.registry.execute_tool_call("echo_tool", "{bad json")

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "invalid_arguments")
        self.assertEqual(result.error.tool_name, "echo_tool")
        self.assertIn("Invalid JSON arguments", result.error.message)

    def test_tool_runtime_error_raises_structured_error(self):
        result = self.registry.execute_tool_call(
            "write_file",
            f'{{"path":"{self.temp_dir.name}","content":"hello"}}',
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "tool_runtime_error")
        self.assertEqual(result.error.tool_name, "write_file")
        self.assertIn("Path is a directory", result.error.message)
