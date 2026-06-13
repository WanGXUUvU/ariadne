import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from agent_prototype.agent.types import AgentDefinition
from agent_prototype.execution.runtime.types import RunState
from agent_prototype.memory.session.store import SessionStore
from agent_prototype.agent.definition import SqliteAgentDefinitionStore
from agent_prototype.api.app import app
from agent_prototype.skills.types import SkillSummary
from agent_prototype.infra.db.engine import get_db
from agent_prototype.infra.db.orm_models import (
    SessionRecord,
    SessionRunEventRecord,
    SessionRunRecord,
)
from agent_prototype.tests.helpers.db import (
    build_test_client,
    make_sqlite_test_db,
    reset_skill_loader_cache,
)
from agent_prototype.tests.helpers.factories import build_assistant_response


class TestAgentApi(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.engine, self.session_local = make_sqlite_test_db(
            self.temp_dir.name,
            "test_agent.db",
        )
        self.client = build_test_client(app, get_db, self.session_local)
        reset_skill_loader_cache()

        # Mock RunContextFactory._create_adapter 绕过物理数据库配置校验，直接返回一个 mock 好的 ChatCompletionsAdapter
        from agent_prototype.execution.run_context_factory import RunContextFactory
        from agent_prototype.core.adapters.chat_completions import ChatCompletionsAdapter

        self.create_adapter_patcher = patch.object(
            RunContextFactory,
            "_create_adapter",
            return_value=ChatCompletionsAdapter(
                api_key="mock-api-key",
                base_url="mock-base-url",
                model="mock-model",
            ),
        )
        self.mock_create_adapter = self.create_adapter_patcher.start()

    def tearDown(self):
        if hasattr(self, "create_adapter_patcher"):
            self.create_adapter_patcher.stop()
        app.dependency_overrides.clear()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def _write_skill(self, source_dir: Path, skill_name: str, content: str):
        skill_dir = source_dir / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    def _assistant_response(self, content=None, tool_calls=None):
        return build_assistant_response(content=content, tool_calls=tool_calls)

    @patch("agent_prototype.core.adapters.chat_completions.ChatCompletionsAdapter.generate")
    def test_run_endpoint(self, mock_generate):
        mock_generate.return_value = self._assistant_response(content="mock reply")
        response = self.client.post("/run", json={"session_id": "session-a", "user_input": "你好"})

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["reply"], "mock reply")
        self.assertEqual(data["state"]["step"], 1)
        self.assertIn("metadata", data)
        self.assertEqual(data["metadata"]["session_id"], "session-a")
        self.assertTrue(data["metadata"]["run_id"])
        self.assertEqual(data["metadata"]["agent_name"], "default")
        self.assertEqual(
            data["state"]["messages"],
            [
                {"role": "user", "content": "你好", "tool_calls": None, "tool_call_id": None},
                {
                    "role": "assistant",
                    "content": "mock reply",
                    "tool_calls": None,
                    "tool_call_id": None,
                },
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

    @patch("agent_prototype.core.adapters.chat_completions.ChatCompletionsAdapter.generate")
    def test_run_endpoint_returns_metadata_with_explicit_agent_and_skill(self, mock_generate):
        mock_generate.return_value = self._assistant_response(content="skill reply")
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

        with (
            patch(
                "agent_prototype.context.skill_context.list_skills",
                return_value=[
                    SkillSummary(
                        name="openai-docs",
                        description="查 OpenAI 官方文档",
                        path="user-codex/openai-docs/SKILL.md",
                        enabled=True,
                    )
                ],
            ),
            patch(
                "agent_prototype.context.skill_context.load_skill_content",
                return_value="FULL SKILL BODY",
            ),
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

    @patch("agent_prototype.core.adapters.chat_completions.ChatCompletionsAdapter.generate")
    def test_compact_endpoint_returns_compacted_state(self, mock_generate):
        mock_generate.return_value = self._assistant_response(content="中段历史摘要")
        db = self.session_local()
        try:
            store = SessionStore(db)
            state = RunState(
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
            store.save_state("compact-session", state=state)
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
        mock_generate.assert_called_once()

    @patch("agent_prototype.core.adapters.chat_completions.ChatCompletionsAdapter.generate")
    def test_run_endpoint_auto_compacts_long_session_before_reply(self, mock_generate):
        mock_generate.side_effect = [
            self._assistant_response(content="自动压缩后的中段摘要"),
            self._assistant_response(content="run reply after auto compact"),
        ]
        db = self.session_local()
        try:
            store = SessionStore(db)
            state = RunState(
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
            store.save_state("auto-compact-session", state=state, context_tokens=90000)
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

        self.assertEqual(mock_generate.call_count, 2)

    @patch("agent_prototype.core.adapters.chat_completions.ChatCompletionsAdapter.generate")
    def test_run_endpoint_does_not_persist_auto_compact_when_run_fails(self, mock_generate):
        mock_generate.side_effect = [
            self._assistant_response(content="自动压缩后的中段摘要"),
            RuntimeError("run failed after auto compact"),
        ]
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
            store = SessionStore(db)
            state = RunState(messages=original_messages)
            store.save_state(
                "auto-compact-fail-session", state=state, context_tokens=90000
            )
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
        self.assertEqual(mock_generate.call_count, 2)

        db = self.session_local()
        try:
            store = SessionStore(db)
            persisted_state = store.read_session_state("auto-compact-fail-session")
            self.assertIsNotNone(persisted_state)
            self.assertEqual(
                [message.model_dump(exclude_none=True) for message in persisted_state.messages],
                original_messages,
            )
        finally:
            db.close()

    @patch("agent_prototype.core.adapters.chat_completions.ChatCompletionsAdapter.generate")
    def test_run_endpoint_updates_session_metadata(self, mock_generate):
        mock_generate.return_value = self._assistant_response(content="mock reply\nwith preview")
        response = self.client.post(
            "/run",
            json={"session_id": "session-meta", "user_input": "你好，简单回复我一句"},
        )

        self.assertEqual(response.status_code, 200)

        db = self.session_local()
        try:
            record = (
                db.query(SessionRecord).filter(SessionRecord.session_id == "session-meta").first()
            )

            self.assertIsNotNone(record)
            self.assertEqual(record.session_id, "session-meta")
            self.assertEqual(record.session_name, "session-meta")
            self.assertEqual(record.last_agent_name, "default")
            self.assertEqual(record.message_count, 2)
            self.assertEqual(record.last_reply_preview, "mock reply with preview")
            self.assertIsNotNone(record.created_at)
            self.assertIsNotNone(record.updated_at)
            self.assertGreaterEqual(record.updated_at, record.created_at)
        finally:
            db.close()

    @patch("agent_prototype.agent.definition.service.AgentDefinitionService.load_definition")
    @patch("agent_prototype.core.adapters.chat_completions.ChatCompletionsAdapter.generate")
    def test_run_endpoint_uses_explicit_agent_name(self, mock_generate, mock_load_definition):
        mock_generate.return_value = self._assistant_response(content="review reply")
        mock_load_definition.return_value = AgentDefinition(
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
        self.assertEqual(mock_load_definition.call_args.args[0], "reviewer")
        self.assertEqual(response.json()["reply"], "review reply")
        self.assertEqual(response.json()["state"]["messages"][0]["role"], "user")
        self.assertEqual(response.json()["state"]["messages"][1]["role"], "assistant")

    @patch(
        "agent_prototype.context.skill_context.load_skill_content",
        return_value="---\nname: openai-docs\ndescription: 查文档\n---\nFULL SKILL BODY",
    )
    @patch("agent_prototype.context.skill_context.list_skills")
    @patch("agent_prototype.core.adapters.chat_completions.ChatCompletionsAdapter.generate")
    def test_run_endpoint_loads_selected_skill_content_into_system_prompt(
        self,
        mock_generate,
        mock_list_skills,
        mock_load_skill_content,
    ):
        mock_generate.return_value = self._assistant_response(content="skill reply")
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

        request = mock_generate.call_args.args[0]
        system_prompt = request.messages[0].content

        self.assertIn("Available skills:", system_prompt)
        self.assertIn("openai-docs: 查 OpenAI 官方文档", system_prompt)
        self.assertIn("Selected skill instructions:", system_prompt)
        self.assertIn("FULL SKILL BODY", system_prompt)

        db = self.session_local()
        try:
            record = (
                db.query(SessionRecord).filter(SessionRecord.session_id == "session-skill").first()
            )
            run_record = (
                db.query(SessionRunRecord)
                .filter(SessionRunRecord.session_id == "session-skill")
                .first()
            )

            self.assertIsNotNone(record)
            self.assertIsNotNone(run_record)
        finally:
            db.close()

    @patch("agent_prototype.context.skill_context.load_skill_content")
    @patch("agent_prototype.context.skill_context.list_skills")
    @patch("agent_prototype.core.adapters.chat_completions.ChatCompletionsAdapter.generate")
    def test_run_endpoint_without_skill_name_only_includes_catalog_prompt(
        self,
        mock_generate,
        mock_list_skills,
        mock_load_skill_content,
    ):
        mock_generate.return_value = self._assistant_response(content="catalog reply")
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

        request = mock_generate.call_args.args[0]
        system_prompt = request.messages[0].content

        self.assertIn("Available skills:", system_prompt)
        self.assertIn("openai-docs: 查 OpenAI 官方文档", system_prompt)
        self.assertNotIn("Selected skill instructions:", system_prompt)
        self.assertNotIn("FULL SKILL BODY", system_prompt)

        db = self.session_local()
        try:
            record = (
                db.query(SessionRecord)
                .filter(SessionRecord.session_id == "session-catalog-only")
                .first()
            )
            run_record = (
                db.query(SessionRunRecord)
                .filter(SessionRunRecord.session_id == "session-catalog-only")
                .first()
            )

            self.assertIsNotNone(record)
            self.assertIsNotNone(run_record)
        finally:
            db.close()

    @patch("agent_prototype.context.skill_context.load_skill_content")
    @patch("agent_prototype.context.skill_context.list_skills")
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
        self.assertEqual(response.json()["error"]["message"], "Skill is disabled: openai-docs")
        mock_load_skill_content.assert_not_called()

    @patch("agent_prototype.context.skill_context.list_skills", return_value=[])
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
        self.assertEqual(data["error"]["message"], "Skill not found: openai-docs")
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
            record = (
                db.query(SessionRecord)
                .filter(SessionRecord.session_id == data["session_id"])
                .first()
            )
            self.assertIsNotNone(record)
            self.assertEqual(record.session_name, "新会话")
            self.assertEqual(record.message_count, 0)
            self.assertIsNone(record.last_agent_name)
            self.assertIsNone(record.last_reply_preview)
        finally:
            db.close()

    @patch("agent_prototype.core.adapters.chat_completions.ChatCompletionsAdapter.generate")
    def test_reset_endpoint_clears_messages_but_keeps_same_session(self, mock_generate):
        mock_generate.return_value = self._assistant_response(content="reset reply")
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
        self.assertIsNone(detail_data["last_reply_preview"])
        self.assertEqual(detail_data["state"]["messages"], [])
        self.assertEqual(detail_data["state"]["step"], 0)
        self.assertIsNone(detail_data["state"]["agent_name"])

        db = self.session_local()
        try:
            record = (
                db.query(SessionRecord).filter(SessionRecord.session_id == "session-reset").first()
            )
            self.assertIsNotNone(record)
            self.assertEqual(record.session_name, "session-reset")
            self.assertEqual(record.message_count, 0)
            self.assertIsNone(record.last_agent_name)
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

    @patch("agent_prototype.core.adapters.chat_completions.ChatCompletionsAdapter.generate")
    def test_delete_session_endpoint_removes_existing_session(self, mock_generate):
        mock_generate.return_value = self._assistant_response(content="delete reply")
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
            record = (
                db.query(SessionRecord).filter(SessionRecord.session_id == "session-delete").first()
            )
            self.assertIsNone(record)
        finally:
            db.close()

    def test_delete_session_endpoint_returns_structured_error_for_missing_session(self):
        response = self.client.delete("/sessions/missing-session")

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data["error"]["code"], "bad_request")
        self.assertEqual(data["error"]["message"], "Session not found")

    @patch("agent_prototype.core.adapters.chat_completions.ChatCompletionsAdapter.generate")
    def test_list_sessions_endpoint_returns_summaries(self, mock_generate):
        mock_generate.return_value = self._assistant_response(content="first reply")
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

    @patch("agent_prototype.core.adapters.chat_completions.ChatCompletionsAdapter.generate")
    def test_read_session_endpoint_returns_detail(self, mock_generate):
        mock_generate.return_value = self._assistant_response(content="detail reply")
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
                {
                    "role": "assistant",
                    "content": "detail reply",
                    "tool_calls": None,
                    "tool_call_id": None,
                },
            ],
        )

    def test_read_session_endpoint_returns_404_for_missing_session(self):
        response = self.client.get("/sessions/missing-session")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "session_not_found")
        self.assertEqual(response.json()["error"]["message"], "Session not found")

    @patch("agent_prototype.skills.loader.get_default_skill_config_path")
    @patch("agent_prototype.skills.loader.get_default_skill_roots")
    def test_list_skills_endpoint_returns_summaries(
        self,
        mock_get_default_skill_roots,
        mock_get_default_skill_config_path,
    ):
        project_skills_root = Path(self.temp_dir.name) / "project-skills"
        user_skills_root = Path(self.temp_dir.name) / "user-skills"
        config_path = Path(self.temp_dir.name) / ".agent" / "skill-config.json"

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
        mock_get_default_skill_config_path.return_value = config_path

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

    @patch("agent_prototype.skills.loader.get_default_skill_config_path")
    @patch("agent_prototype.skills.loader.get_default_skill_roots")
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
        self.assertEqual(
            config_path.read_text(encoding="utf-8"), '{\n  "disabled": [\n    "Alpha Skill"\n  ]\n}'
        )

        list_response = self.client.get("/skills")

        self.assertEqual(list_response.status_code, 200)
        self.assertFalse(list_response.json()[0]["enabled"])

        enable_response = self.client.post("/skills/Alpha Skill/enable")

        self.assertEqual(enable_response.status_code, 200)
        self.assertTrue(enable_response.json()["enabled"])
        self.assertEqual(config_path.read_text(encoding="utf-8"), '{\n  "disabled": []\n}')

    @patch("agent_prototype.core.adapters.chat_completions.ChatCompletionsAdapter.generate")
    def test_trace_endpoint_returns_runs_in_order(self, mock_generate):
        mock_generate.return_value = self._assistant_response(content="trace reply")
        first_response = self.client.post(
            "/run", json={"session_id": "trace-session", "user_input": "第一轮"}
        )
        second_response = self.client.post(
            "/run", json={"session_id": "trace-session", "user_input": "第二轮"}
        )

        response = self.client.get("/sessions/trace-session/trace")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["session_id"], "trace-session")
        self.assertEqual(
            [run["run_id"] for run in data["runs"]],
            [
                first_response.json()["metadata"]["run_id"],
                second_response.json()["metadata"]["run_id"],
            ],
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

    @patch("agent_prototype.core.adapters.chat_completions.ChatCompletionsAdapter.generate")
    def test_trace_endpoint_supports_run_id_filter(self, mock_generate):
        mock_generate.return_value = self._assistant_response(content="filtered trace reply")
        first_response = self.client.post(
            "/run", json={"session_id": "trace-filter", "user_input": "第一轮"}
        )
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

    def test_rename_session_endpoint_updates_name(self):
        # 先创建 session
        create_resp = self.client.post("/sessions", json={"session_name": "旧名字"})
        self.assertEqual(create_resp.status_code, 200)
        session_id = create_resp.json()["session_id"]

        # 发送重命名请求
        rename_resp = self.client.patch(
            f"/sessions/{session_id}",
            json={"session_name": "新名字"},
        )
        self.assertEqual(rename_resp.status_code, 200)
        self.assertEqual(rename_resp.json(), {"ok": True})

        # 确认名称已持久化
        detail_resp = self.client.get(f"/sessions/{session_id}")
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.json()["session_name"], "新名字")

    def test_rename_session_endpoint_returns_error_for_empty_name(self):
        create_resp = self.client.post("/sessions", json={"session_name": "测试会话"})
        session_id = create_resp.json()["session_id"]

        rename_resp = self.client.patch(
            f"/sessions/{session_id}",
            json={"session_name": "   "},  # 空白字符串
        )
        self.assertEqual(rename_resp.status_code, 400)
        self.assertEqual(rename_resp.json()["error"]["code"], "bad_request")

    def test_rename_session_endpoint_returns_error_for_missing_session(self):
        rename_resp = self.client.patch(
            "/sessions/nonexistent-id",
            json={"session_name": "新名字"},
        )
        self.assertEqual(rename_resp.status_code, 400)
        self.assertEqual(rename_resp.json()["error"]["code"], "bad_request")
