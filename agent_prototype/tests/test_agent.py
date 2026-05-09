import unittest
import tempfile
import requests
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agent_prototype.runtime.agent import Agent
from agent_prototype.core.agent_definition import AgentDefinition
from agent_prototype.core.schemas import AgentInput, AgentState, SkillSummary
from agent_prototype.storage.session_store import SqliteSessionStore
from agent_prototype.storage.agent_definition_store import SqliteAgentDefinitionStore
from agent_prototype.api.app import app
from agent_prototype.runtime.llm_client import call_llm
from agent_prototype.runtime.agent_loader import load_agent_definition
from agent_prototype.runtime.skill_loader import list_skills
from agent_prototype.runtime.tool_registry import build_default_tool_registry
from agent_prototype.storage.db import Base, get_db
from agent_prototype.storage.models import SessionRecord, SessionRunEventRecord, SessionRunRecord


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


class TestLlmClient(unittest.TestCase):
    @patch.dict("os.environ", {"SENSENOVA_API_KEY": "test-key"}, clear=False)
    @patch("agent_prototype.runtime.llm_client.requests.post")
    def test_call_llm_wraps_http_error_with_runtime_error(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "upstream failed"
        mock_response.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
        mock_post.return_value = mock_response

        with self.assertRaises(RuntimeError) as ctx:
            call_llm([{"role": "user", "content": "你好"}])

        self.assertIn("LLM request failed", str(ctx.exception))
        self.assertIn("status=500", str(ctx.exception))
        self.assertIn("body=upstream failed", str(ctx.exception))
        mock_response.raise_for_status.assert_called_once()
        mock_response.json.assert_not_called()

    @patch.dict("os.environ", {"SENSENOVA_API_KEY": "test-key"}, clear=False)
    @patch("agent_prototype.runtime.llm_client.requests.post")
    def test_call_llm_raises_when_choices_missing(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {}
        mock_post.return_value = mock_response

        with self.assertRaises(ValueError) as ctx:
            call_llm([{"role": "user", "content": "你好"}])

        self.assertEqual(str(ctx.exception), "LLM response missing choices")

    @patch.dict("os.environ", {"SENSENOVA_API_KEY": "test-key"}, clear=False)
    @patch("agent_prototype.runtime.llm_client.requests.post")
    def test_call_llm_raises_when_message_missing(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"choices": [{}]}
        mock_post.return_value = mock_response

        with self.assertRaises(ValueError) as ctx:
            call_llm([{"role": "user", "content": "你好"}])

        self.assertEqual(str(ctx.exception), "LLM response missing message")


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


class TestSkillLoader(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_skill(self, source_dir: Path, skill_name: str, content: str):
        skill_dir = source_dir / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    def test_list_skills_returns_enabled_and_disabled_entries(self):
        project_skills_root = self.root_path / "project-skills"
        user_skills_root = self.root_path / "user-skills"

        self._write_skill(
            project_skills_root,
            "alpha-skill",
            "---\nname: Alpha Skill\ndescription: Alpha summary\n---\n# Alpha\n",
        )
        self._write_skill(
            user_skills_root,
            "broken-skill",
            "name: Broken Skill\n# Missing frontmatter\n",
        )

        results = list_skills(
            [
                ("project-opencode", project_skills_root),
                ("user-codex", user_skills_root),
            ]
        )

        self.assertEqual(len(results), 2)

        by_name = {item.name: item for item in results}

        self.assertIn("Alpha Skill", by_name)
        self.assertTrue(by_name["Alpha Skill"].enabled)
        self.assertEqual(by_name["Alpha Skill"].description, "Alpha summary")
        self.assertEqual(by_name["Alpha Skill"].path, "project-opencode/alpha-skill/SKILL.md")
        self.assertIsNone(by_name["Alpha Skill"].error)

        self.assertIn("broken-skill", by_name)
        self.assertFalse(by_name["broken-skill"].enabled)
        self.assertEqual(by_name["broken-skill"].path, "user-codex/broken-skill/SKILL.md")
        self.assertIn("Missing frontmatter", by_name["broken-skill"].error)

    def test_list_skills_applies_disabled_config(self):
        project_skills_root = self.root_path / "project-skills"
        config_path = self.root_path / "skill-config.json"

        self._write_skill(
            project_skills_root,
            "alpha-skill",
            "---\nname: Alpha Skill\ndescription: Alpha summary\n---\n# Alpha\n",
        )
        config_path.write_text('{"disabled": ["Alpha Skill"]}', encoding="utf-8")

        results = list_skills(
            [("project-opencode", project_skills_root)],
            config_path=config_path,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Alpha Skill")
        self.assertFalse(results[0].enabled)


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

    def _write_skill(self, source_dir: Path, skill_name: str, content: str):
        skill_dir = source_dir / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    @patch("agent_prototype.runtime.agent.call_llm", return_value={"role": "assistant", "content": "mock reply"})
    def test_run_endpoint(self, mock_call_llm):
        response = self.client.post("/run", json={"session_id": "session-a", "user_input": "你好"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["reply"], "mock reply")
        self.assertEqual(data["state"]["step"], 1)
        self.assertIn("metadata", data)
        self.assertEqual(data["metadata"]["session_id"], "session-a")
        self.assertTrue(data["metadata"]["run_id"])
        self.assertEqual(data["metadata"]["agent_name"], "default")
        self.assertIsNone(data["metadata"]["skill_name"])
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

    @patch("agent_prototype.runtime.agent.call_llm", return_value={"role": "assistant", "content": "skill reply"})
    def test_run_endpoint_returns_metadata_with_explicit_agent_and_skill(self, mock_call_llm):
        db = self.session_local()
        try:
            store = SqliteAgentDefinitionStore(db)
            store.save(
                AgentDefinition(
                    id="reviewer",
                    name="Reviewer Agent",
                    system_prompt="你是一个严格的代码审查助手",
                    description="review mode",
                    tool_names=[],
                )
            )
            db.commit()
        finally:
            db.close()

        with patch(
            "agent_prototype.runtime.services.list_skills",
            return_value=[
                SkillSummary(
                    name="openai-docs",
                    description="查 OpenAI 官方文档",
                    path="user-codex/openai-docs/SKILL.md",
                    enabled=True,
                )
            ],
        ), patch(
            "agent_prototype.runtime.services.load_skill_content",
            return_value="FULL SKILL BODY",
        ):
            response = self.client.post(
                "/run",
                json={
                    "session_id": "session-with-metadata",
                    "user_input": "帮我审查并查文档",
                    "agent_name": "reviewer",
                    "skill_name": "openai-docs",
                },
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["metadata"]["session_id"], "session-with-metadata")
        self.assertTrue(data["metadata"]["run_id"])
        self.assertEqual(data["metadata"]["agent_name"], "reviewer")
        self.assertEqual(data["metadata"]["skill_name"], "openai-docs")

    @patch("agent_prototype.runtime.services.call_llm", return_value={"role": "assistant", "content": "中段历史摘要"})
    def test_compact_endpoint_returns_compacted_state(self, mock_call_llm):
        db = self.session_local()
        try:
            store = SqliteSessionStore(db)
            state = AgentState(
                messages=[
                    {"role": "user", "content": "最初任务目标"},
                    {"role": "assistant", "content": "好的，我们先拆任务"},
                    {"role": "user", "content": "我需要支持 tool calling"},
                    {"role": "assistant", "content": "我们需要看 OpenAI 文档"},
                    {"role": "tool", "content": "tool result: Responses API docs"},
                    {"role": "assistant", "content": "我们再确认一遍上下文压缩策略"},
                    {"role": "user", "content": "我要保留关键约束"},
                    {"role": "assistant", "content": "好的，关键约束需要进入摘要"},
                    {"role": "tool", "content": "tool result: compact best practices"},
                    {"role": "user", "content": "还要保留最近原始消息"},
                    {"role": "assistant", "content": "明白，我们采用三段式策略"},
                    {"role": "user", "content": "继续准备自动 compact"},
                    {"role": "assistant", "content": "自动 compact 会在 /run 前触发"},
                    {"role": "user", "content": "现在开始做 compact"},
                ]
            )
            store.upsert_session_snapshot("compact-session", state=state)
            db.commit()
        finally:
            db.close()

        response = self.client.post(
            "/compact",
            json={
                "session_id": "compact-session",
                "trigger_threshold": 4,
                "keep_recent_count": 2,
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["did_compact"])
        self.assertEqual(data["state"]["messages"][0]["content"], "最初任务目标")
        self.assertEqual(data["state"]["messages"][1]["role"], "system")
        self.assertIn("中段历史摘要", data["state"]["messages"][1]["content"])
        self.assertEqual(data["state"]["messages"][-2]["content"], "自动 compact 会在 /run 前触发")
        self.assertEqual(data["state"]["messages"][-1]["content"], "现在开始做 compact")
        mock_call_llm.assert_called_once()

    @patch(
        "agent_prototype.runtime.agent.call_llm",
        return_value={"role": "assistant", "content": "run reply after auto compact"},
    )
    @patch("agent_prototype.runtime.services.call_llm", return_value={"role": "assistant", "content": "自动压缩后的中段摘要"})
    def test_run_endpoint_auto_compacts_long_session_before_reply(self, mock_compact_call_llm, mock_run_call_llm):
        db = self.session_local()
        try:
            store = SqliteSessionStore(db)
            state = AgentState(
                messages=[
                    {"role": "user", "content": "最初任务目标"},
                    {"role": "assistant", "content": "好的，我们先拆任务"},
                    {"role": "user", "content": "我需要支持 tool calling"},
                    {"role": "assistant", "content": "我们需要看 OpenAI 文档"},
                    {"role": "tool", "content": "tool result: Responses API docs"},
                    {"role": "assistant", "content": "我们再确认一遍上下文压缩策略"},
                    {"role": "user", "content": "我要保留关键约束"},
                    {"role": "assistant", "content": "好的，关键约束需要进入摘要"},
                    {"role": "tool", "content": "tool result: compact best practices"},
                    {"role": "user", "content": "还要保留最近原始消息"},
                    {"role": "assistant", "content": "明白，我们采用三段式策略"},
                    {"role": "user", "content": "继续准备自动 compact"},
                    {"role": "assistant", "content": "自动 compact 会在 /run 前触发"},
                    {"role": "user", "content": "现在开始做 compact"},
                ]
            )
            store.upsert_session_snapshot("auto-compact-session", state=state)
            db.commit()
        finally:
            db.close()

        response = self.client.post(
            "/run",
            json={
                "session_id": "auto-compact-session",
                "user_input": "继续执行下一步",
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["reply"], "run reply after auto compact")

        compacted_messages = data["state"]["messages"]
        self.assertEqual(compacted_messages[0]["content"], "最初任务目标")
        self.assertEqual(compacted_messages[1]["role"], "system")
        self.assertIn("自动压缩后的中段摘要", compacted_messages[1]["content"])
        self.assertEqual(compacted_messages[-2]["role"], "user")
        self.assertEqual(compacted_messages[-2]["content"], "继续执行下一步")
        self.assertEqual(compacted_messages[-1]["role"], "assistant")
        self.assertEqual(compacted_messages[-1]["content"], "run reply after auto compact")

        mock_compact_call_llm.assert_called_once()
        mock_run_call_llm.assert_called_once()

    @patch(
        "agent_prototype.runtime.agent.call_llm",
        side_effect=RuntimeError("run failed after auto compact"),
    )
    @patch("agent_prototype.runtime.services.call_llm", return_value={"role": "assistant", "content": "自动压缩后的中段摘要"})
    def test_run_endpoint_does_not_persist_auto_compact_when_run_fails(self, mock_compact_call_llm, mock_run_call_llm):
        original_messages = [
            {"role": "user", "content": "最初任务目标"},
            {"role": "assistant", "content": "好的，我们先拆任务"},
            {"role": "user", "content": "我需要支持 tool calling"},
            {"role": "assistant", "content": "我们需要看 OpenAI 文档"},
            {"role": "tool", "content": "tool result: Responses API docs"},
            {"role": "assistant", "content": "我们再确认一遍上下文压缩策略"},
            {"role": "user", "content": "我要保留关键约束"},
            {"role": "assistant", "content": "好的，关键约束需要进入摘要"},
            {"role": "tool", "content": "tool result: compact best practices"},
            {"role": "user", "content": "还要保留最近原始消息"},
            {"role": "assistant", "content": "明白，我们采用三段式策略"},
            {"role": "user", "content": "继续准备自动 compact"},
            {"role": "assistant", "content": "自动 compact 会在 /run 前触发"},
            {"role": "user", "content": "现在开始做 compact"},
        ]

        db = self.session_local()
        try:
            store = SqliteSessionStore(db)
            state = AgentState(messages=original_messages)
            store.upsert_session_snapshot("auto-compact-fail-session", state=state)
            db.commit()
        finally:
            db.close()

        with self.assertRaises(RuntimeError) as ctx:
            self.client.post(
                "/run",
                json={
                    "session_id": "auto-compact-fail-session",
                    "user_input": "继续执行下一步",
                },
            )

        self.assertIn("run failed after auto compact", str(ctx.exception))
        mock_compact_call_llm.assert_called_once()
        mock_run_call_llm.assert_called_once()

        db = self.session_local()
        try:
            store = SqliteSessionStore(db)
            persisted_state = store.read_session_state("auto-compact-fail-session")
            self.assertIsNotNone(persisted_state)
            self.assertEqual(
                [message.model_dump(exclude_none=True) for message in persisted_state.messages],
                original_messages,
            )
        finally:
            db.close()

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

    @patch("agent_prototype.runtime.services.load_skill_content", return_value="---\nname: openai-docs\ndescription: 查文档\n---\nFULL SKILL BODY")
    @patch("agent_prototype.runtime.services.list_skills")
    @patch("agent_prototype.runtime.agent.call_llm", return_value={"role": "assistant", "content": "skill reply"})
    def test_run_endpoint_loads_selected_skill_content_into_system_prompt(
        self,
        mock_call_llm,
        mock_list_skills,
        mock_load_skill_content,
    ):
        mock_list_skills.return_value = [
            SkillSummary(
                name="openai-docs",
                description="查 OpenAI 官方文档",
                path="user-codex/openai-docs/SKILL.md",
                enabled=True,
            )
        ]

        response = self.client.post(
            "/run",
            json={
                "session_id": "session-skill",
                "user_input": "帮我查文档",
                "skill_name": "openai-docs",
            },
        )

        self.assertEqual(response.status_code, 200)
        mock_load_skill_content.assert_called_once_with("openai-docs")

        messages = mock_call_llm.call_args.args[0]
        system_prompt = messages[0]["content"]

        self.assertIn("Available skills:", system_prompt)
        self.assertIn("openai-docs: 查 OpenAI 官方文档", system_prompt)
        self.assertIn("Selected skill instructions:", system_prompt)
        self.assertIn("FULL SKILL BODY", system_prompt)

        db = self.session_local()
        try:
            record = db.query(SessionRecord).filter(SessionRecord.session_id == "session-skill").first()
            run_record = db.query(SessionRunRecord).filter(SessionRunRecord.session_id == "session-skill").first()

            self.assertIsNotNone(record)
            self.assertEqual(record.last_skill_name, "openai-docs")
            self.assertIsNotNone(run_record)
            self.assertEqual(run_record.skill_name, "openai-docs")
        finally:
            db.close()

    @patch("agent_prototype.runtime.services.load_skill_content")
    @patch("agent_prototype.runtime.services.list_skills")
    @patch("agent_prototype.runtime.agent.call_llm", return_value={"role": "assistant", "content": "catalog reply"})
    def test_run_endpoint_without_skill_name_only_includes_catalog_prompt(
        self,
        mock_call_llm,
        mock_list_skills,
        mock_load_skill_content,
    ):
        mock_list_skills.return_value = [
            SkillSummary(
                name="openai-docs",
                description="查 OpenAI 官方文档",
                path="user-codex/openai-docs/SKILL.md",
                enabled=True,
            )
        ]

        response = self.client.post(
            "/run",
            json={
                "session_id": "session-catalog-only",
                "user_input": "帮我查文档",
            },
        )

        self.assertEqual(response.status_code, 200)
        mock_load_skill_content.assert_not_called()

        messages = mock_call_llm.call_args.args[0]
        system_prompt = messages[0]["content"]

        self.assertIn("Available skills:", system_prompt)
        self.assertIn("openai-docs: 查 OpenAI 官方文档", system_prompt)
        self.assertNotIn("Selected skill instructions:", system_prompt)
        self.assertNotIn("FULL SKILL BODY", system_prompt)

        db = self.session_local()
        try:
            record = db.query(SessionRecord).filter(SessionRecord.session_id == "session-catalog-only").first()
            run_record = db.query(SessionRunRecord).filter(SessionRunRecord.session_id == "session-catalog-only").first()

            self.assertIsNotNone(record)
            self.assertIsNone(record.last_skill_name)
            self.assertIsNotNone(run_record)
            self.assertIsNone(run_record.skill_name)
        finally:
            db.close()

    @patch("agent_prototype.runtime.services.load_skill_content")
    @patch("agent_prototype.runtime.services.list_skills")
    def test_run_endpoint_rejects_disabled_skill_before_loading_content(
        self,
        mock_list_skills,
        mock_load_skill_content,
    ):
        mock_list_skills.return_value = [
            SkillSummary(
                name="openai-docs",
                description="查 OpenAI 官方文档",
                path="user-codex/openai-docs/SKILL.md",
                enabled=False,
            )
        ]

        response = self.client.post(
            "/run",
            json={
                "session_id": "session-disabled-skill",
                "user_input": "帮我查文档",
                "skill_name": "openai-docs",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "bad_request")
        self.assertEqual(response.json()["error"]["message"], "Skill is disabled:openai-docs")
        mock_load_skill_content.assert_not_called()

    @patch("agent_prototype.runtime.services.list_skills", return_value=[])
    def test_run_endpoint_returns_structured_error_when_skill_not_found(self, mock_list_skills):
        response = self.client.post(
            "/run",
            json={
                "session_id": "session-missing-skill",
                "user_input": "帮我查文档",
                "skill_name": "openai-docs",
            },
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error"]["code"], "bad_request")
        self.assertEqual(data["error"]["message"], "Skill not found:openai-docs")
        mock_list_skills.assert_called_once()

    def test_create_session_endpoint_returns_summary_and_persists_empty_session(self):
        response = self.client.post(
            "/sessions",
            json={"session_name": "新会话"},
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertTrue(data["session_id"])
        self.assertEqual(data["session_name"], "新会话")
        self.assertEqual(data["message_count"], 0)
        self.assertIsNone(data["last_agent_name"])
        self.assertIsNone(data["last_skill_name"])
        self.assertIsNone(data["last_reply_preview"])
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)

        list_response = self.client.get("/sessions")
        self.assertEqual(list_response.status_code, 200)

        sessions = list_response.json()
        created_session = next(
            item for item in sessions if item["session_id"] == data["session_id"]
        )

        self.assertEqual(created_session["session_name"], "新会话")
        self.assertEqual(created_session["message_count"], 0)
        self.assertIsNone(created_session["last_reply_preview"])

        db = self.session_local()
        try:
            record = db.query(SessionRecord).filter(SessionRecord.session_id == data["session_id"]).first()
            self.assertIsNotNone(record)
            self.assertEqual(record.session_name, "新会话")
            self.assertEqual(record.message_count, 0)
            self.assertIsNone(record.last_agent_name)
            self.assertIsNone(record.last_skill_name)
            self.assertIsNone(record.last_reply_preview)
        finally:
            db.close()

    @patch("agent_prototype.runtime.agent.call_llm", return_value={"role": "assistant", "content": "reset reply"})
    def test_reset_endpoint_clears_messages_but_keeps_same_session(self, mock_call_llm):
        self.client.post(
            "/run",
            json={"session_id": "session-reset", "user_input": "你好"},
        )

        response = self.client.post(
            "/reset",
            json={"session_id": "session-reset"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

        detail_response = self.client.get("/sessions/session-reset")
        self.assertEqual(detail_response.status_code, 200)
        detail_data = detail_response.json()

        self.assertEqual(detail_data["session_id"], "session-reset")
        self.assertEqual(detail_data["session_name"], "session-reset")
        self.assertEqual(detail_data["message_count"], 0)
        self.assertIsNone(detail_data["last_agent_name"])
        self.assertIsNone(detail_data["last_skill_name"])
        self.assertIsNone(detail_data["last_reply_preview"])
        self.assertEqual(detail_data["state"]["messages"], [])
        self.assertEqual(detail_data["state"]["step"], 0)
        self.assertIsNone(detail_data["state"]["agent_name"])

        db = self.session_local()
        try:
            record = db.query(SessionRecord).filter(SessionRecord.session_id == "session-reset").first()
            self.assertIsNotNone(record)
            self.assertEqual(record.session_name, "session-reset")
            self.assertEqual(record.message_count, 0)
            self.assertIsNone(record.last_agent_name)
            self.assertIsNone(record.last_skill_name)
            self.assertIsNone(record.last_reply_preview)
        finally:
            db.close()

    def test_reset_endpoint_returns_structured_error_for_missing_session(self):
        response = self.client.post(
            "/reset",
            json={"session_id": "missing-session"},
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error"]["code"], "bad_request")
        self.assertEqual(data["error"]["message"], "Session not found")

    @patch("agent_prototype.runtime.agent.call_llm", return_value={"role": "assistant", "content": "delete reply"})
    def test_delete_session_endpoint_removes_existing_session(self, mock_call_llm):
        self.client.post(
            "/run",
            json={"session_id": "session-delete", "user_input": "你好"},
        )

        response = self.client.delete("/sessions/session-delete")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

        detail_response = self.client.get("/sessions/session-delete")
        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(detail_response.json()["error"]["code"], "session_not_found")

        list_response = self.client.get("/sessions")
        self.assertEqual(list_response.status_code, 200)
        session_ids = [item["session_id"] for item in list_response.json()]
        self.assertNotIn("session-delete", session_ids)

        db = self.session_local()
        try:
            record = db.query(SessionRecord).filter(SessionRecord.session_id == "session-delete").first()
            self.assertIsNone(record)
        finally:
            db.close()

    def test_delete_session_endpoint_returns_structured_error_for_missing_session(self):
        response = self.client.delete("/sessions/missing-session")

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error"]["code"], "bad_request")
        self.assertEqual(data["error"]["message"], "Session not found")

    @patch("agent_prototype.runtime.agent.call_llm", return_value={"role": "assistant", "content": "first reply"})
    def test_list_sessions_endpoint_returns_summaries(self, mock_call_llm):
        self.client.post("/run", json={"session_id": "session-b", "user_input": "你好"})
        self.client.post("/run", json={"session_id": "session-a", "user_input": "你好"})
        import time
        time.sleep(1)
        self.client.post("/run", json={"session_id": "session-b", "user_input": "再来一次"})

        response = self.client.get("/sessions")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["session_id"], "session-b")
        self.assertEqual(data[1]["session_id"], "session-a")
        self.assertNotIn("state_json", data[0])
        self.assertEqual(data[0]["message_count"], 4)
        self.assertEqual(data[0]["last_reply_preview"], "first reply")
        self.assertEqual(data[0]["last_agent_name"], "default")
        self.assertIn("created_at", data[0])
        self.assertIn("updated_at", data[0])

    @patch("agent_prototype.runtime.agent.call_llm", return_value={"role": "assistant", "content": "detail reply"})
    def test_read_session_endpoint_returns_detail(self, mock_call_llm):
        self.client.post("/run", json={"session_id": "session-detail", "user_input": "你好"})

        response = self.client.get("/sessions/session-detail")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["session_id"], "session-detail")
        self.assertEqual(data["session_name"], "session-detail")
        self.assertEqual(data["message_count"], 2)
        self.assertEqual(data["state"]["step"], 1)
        self.assertEqual(
            data["state"]["messages"],
            [
                {"role": "user", "content": "你好", "tool_calls": None, "tool_call_id": None},
                {"role": "assistant", "content": "detail reply", "tool_calls": None, "tool_call_id": None},
            ],
        )

    def test_read_session_endpoint_returns_404_for_missing_session(self):
        response = self.client.get("/sessions/missing-session")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "session_not_found")
        self.assertEqual(response.json()["error"]["message"], "Session not found")

    @patch("agent_prototype.runtime.skill_loader.get_default_skill_roots")
    def test_list_skills_endpoint_returns_summaries(self, mock_get_default_skill_roots):
        project_skills_root = Path(self.temp_dir.name) / "project-skills"
        user_skills_root = Path(self.temp_dir.name) / "user-skills"

        self._write_skill(
            project_skills_root,
            "alpha-skill",
            "---\nname: Alpha Skill\ndescription: Alpha summary\n---\n# Alpha\n",
        )
        self._write_skill(
            user_skills_root,
            "broken-skill",
            "name: Broken Skill\n# Missing frontmatter\n",
        )

        mock_get_default_skill_roots.return_value = [
            ("project-opencode", project_skills_root),
            ("user-codex", user_skills_root),
        ]

        response = self.client.get("/skills")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)

        by_name = {item["name"]: item for item in data}

        self.assertEqual(by_name["Alpha Skill"]["description"], "Alpha summary")
        self.assertEqual(by_name["Alpha Skill"]["path"], "project-opencode/alpha-skill/SKILL.md")
        self.assertTrue(by_name["Alpha Skill"]["enabled"])
        self.assertIsNone(by_name["Alpha Skill"]["error"])

        self.assertFalse(by_name["broken-skill"]["enabled"])
        self.assertEqual(by_name["broken-skill"]["path"], "user-codex/broken-skill/SKILL.md")
        self.assertIn("Missing frontmatter", by_name["broken-skill"]["error"])

    @patch("agent_prototype.runtime.skill_loader.get_default_skill_config_path")
    @patch("agent_prototype.runtime.skill_loader.get_default_skill_roots")
    def test_disable_and_enable_skill_endpoints_update_config(
        self,
        mock_get_default_skill_roots,
        mock_get_default_skill_config_path,
    ):
        project_skills_root = Path(self.temp_dir.name) / "project-skills"
        config_path = Path(self.temp_dir.name) / ".agent" / "skill-config.json"

        self._write_skill(
            project_skills_root,
            "alpha-skill",
            "---\nname: Alpha Skill\ndescription: Alpha summary\n---\n# Alpha\n",
        )
        mock_get_default_skill_roots.return_value = [("project-opencode", project_skills_root)]
        mock_get_default_skill_config_path.return_value = config_path

        disable_response = self.client.post("/skills/Alpha Skill/disable")

        self.assertEqual(disable_response.status_code, 200)
        self.assertFalse(disable_response.json()["enabled"])
        self.assertEqual(config_path.read_text(encoding="utf-8"), '{\n  "disabled": [\n    "Alpha Skill"\n  ]\n}')

        list_response = self.client.get("/skills")

        self.assertEqual(list_response.status_code, 200)
        self.assertFalse(list_response.json()[0]["enabled"])

        enable_response = self.client.post("/skills/Alpha Skill/enable")

        self.assertEqual(enable_response.status_code, 200)
        self.assertTrue(enable_response.json()["enabled"])
        self.assertEqual(config_path.read_text(encoding="utf-8"), '{\n  "disabled": []\n}')

    @patch("agent_prototype.runtime.agent.call_llm", return_value={"role": "assistant", "content": "trace reply"})
    def test_trace_endpoint_returns_runs_in_order(self, mock_call_llm):
        first_response = self.client.post("/run", json={"session_id": "trace-session", "user_input": "第一轮"})
        second_response = self.client.post("/run", json={"session_id": "trace-session", "user_input": "第二轮"})

        response = self.client.get("/sessions/trace-session/trace")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["session_id"], "trace-session")
        self.assertEqual(
            [run["run_id"] for run in data["runs"]],
            [first_response.json()["metadata"]["run_id"], second_response.json()["metadata"]["run_id"]],
        )
        self.assertEqual([run["user_input"] for run in data["runs"]], ["第一轮", "第二轮"])
        self.assertEqual(data["runs"][0]["event_count"], 1)
        self.assertEqual(data["runs"][0]["events"][0]["type"], "final_answer")
        self.assertEqual(data["runs"][0]["events"][0]["content"], "trace reply")
        self.assertIn("created_at", data["runs"][0])
        self.assertIn("finished_at", data["runs"][0])

        db = self.session_local()
        try:
            self.assertEqual(db.query(SessionRunRecord).count(), 2)
            self.assertEqual(db.query(SessionRunEventRecord).count(), 2)
        finally:
            db.close()

    @patch("agent_prototype.runtime.agent.call_llm", return_value={"role": "assistant", "content": "filtered trace reply"})
    def test_trace_endpoint_supports_run_id_filter(self, mock_call_llm):
        first_response = self.client.post("/run", json={"session_id": "trace-filter", "user_input": "第一轮"})
        self.client.post("/run", json={"session_id": "trace-filter", "user_input": "第二轮"})

        response = self.client.get(
            f"/sessions/trace-filter/trace?run_id={first_response.json()['metadata']['run_id']}"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["runs"]), 1)
        self.assertEqual(data["runs"][0]["run_id"], first_response.json()["metadata"]["run_id"])
        self.assertEqual(data["runs"][0]["user_input"], "第一轮")

    def test_trace_endpoint_returns_404_for_missing_trace(self):
        response = self.client.get("/sessions/missing-session/trace")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "trace_not_found")
        self.assertEqual(response.json()["error"]["message"], "Trace not found")


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
