"""测试 spawn_child_agent 工具和 build_run_registry。

覆盖：
1. build_run_registry 注册了 spawn_child_agent / check / wait
2. spawn_child_agent 异步提交，返回 child_run_id，子 run 落库后 parent_run_id 正确
3. get_children_runs 能查出正确的子 run
"""

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch, MagicMock

from agent_prototype.infra.db.orm_models import ModelSetting, ProviderConfig
from agent_prototype.execution.runtime.types import RunState, RunEvent
from agent_prototype.memory.session.store import SessionStore
from agent_prototype.memory.run.store import RunTraceStore
from agent_prototype.tools.registry import build_run_registry
from agent_prototype.execution.service import RunService
from agent_prototype.tests.helpers.db import make_sqlite_test_db
from agent_prototype.tests.helpers.factories import build_run_output


def _seed_session_model(session_local, session_id: str, model_id: str = "test-model") -> None:
    db = session_local()
    try:
        provider = ProviderConfig(
            name="default-provider",
            base_url="https://example.com/v1",
            api_key="test-key",
            is_default=1,
        )
        db.add(provider)
        db.flush()

        model = ModelSetting(
            provider_id=provider.id,
            model_id=model_id,
            display_name="Test Model",
            enabled=1,
            supports_thinking=0,
            thinking_style="none",
            effort_levels="[]",
            context_length=4096,
            supports_tools=1,
        )
        db.add(model)
        db.flush()

        store = SessionStore(db)
        record = store.save_state(session_id, state=RunState())
        record.model_provider_id = provider.id
        record.model_id = model_id
        db.commit()
    finally:
        db.close()


class TestBuildRunRegistry(unittest.TestCase):
    """build_run_registry 注册了 spawn_child_agent / check / wait。"""

    def test_spawn_child_agent_in_schema_list(self):
        registry = build_run_registry(
            child_dispatcher=lambda t, a: "child-id",
            status_checker=lambda ids: {},
            child_waiter=lambda cid: "reply",
        )
        tool_names = [s["function"]["name"] for s in registry.get_tool_schemas()]
        self.assertIn("spawn_child_agent", tool_names)
        self.assertIn("check_child_status", tool_names)
        self.assertIn("wait_child_agent", tool_names)

    def test_spawn_child_agent_not_in_default_registry(self):
        """默认 registry 没有 spawn_child_agent，确保它是动态注册的。"""
        from agent_prototype.tools.registry import build_default_tool_registry

        registry = build_default_tool_registry()
        tool_names = [s["function"]["name"] for s in registry.get_tool_schemas()]
        self.assertNotIn("spawn_child_agent", tool_names)


class TestSpawnChildAgentPersistence(unittest.TestCase):
    """spawn_child_agent 异步执行后子 run 落库，parent_run_id 指向父 run。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine, self.session_local = make_sqlite_test_db(
            self.temp.name,
            "test_spawn.db",
        )
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.futures = {}

    def tearDown(self):
        self.executor.shutdown(wait=False)
        self.engine.dispose()
        self.temp.cleanup()

    def test_child_run_persisted_with_correct_parent_run_id(self):
        parent_run_id = "parent-run-abc"
        session_id = "session-with-model"
        _seed_session_model(self.session_local, session_id)
        fake_output = build_run_output(
            "子任务完成",
            events=[RunEvent(index=0, type="final_answer", content="子任务完成")],
        )

        db = self.session_local()
        run_service = RunService(db)

        # 核心修复：通过 patch "run_service.AgentRunner" 来正确 mock 线程中实例化的类，并重定向 DB 操作为测试内存库
        with (
            patch("agent_prototype.execution.child_run_launcher._executor", self.executor),
            patch("agent_prototype.execution.child_run_launcher._global_futures", self.futures),
            patch("agent_prototype.execution.child_run_launcher.AgentRunner") as MockAgent,
            patch("agent_prototype.execution.child_run_launcher.RunVfsRegistry") as MockVfsRegistry,
            patch("agent_prototype.execution.persistence.run_recorder.RunVfsRegistry") as MockPersistVfsRegistry,
            patch(
                "agent_prototype.execution.child_run_launcher.SessionLocal", self.session_local
            ),
        ):

            mock_instance = MagicMock()
            mock_instance.execute.return_value = fake_output
            MockAgent.return_value = mock_instance
            staged_vfs = MagicMock()
            MockPersistVfsRegistry.get.return_value = staged_vfs

            registry = build_run_registry(
                child_dispatcher=run_service.child_dispatcher.create_launcher(
                    parent_run_id, session_id
                ),
                status_checker=run_service.child_dispatcher.create_status_checker(),
                child_waiter=run_service.child_dispatcher.create_waiter(),
            )
            result = registry.execute_tool_call(
                "spawn_child_agent",
                '{"task": "帮我查一下天气"}',
            )

            self.assertTrue(result.ok)
            child_run_id = result.content  # spawn 现在立即返回 child_run_id

            # 等待子线程完成
            self.futures[child_run_id].result(timeout=10)

        try:
            run_store = RunTraceStore(db)
            children = run_store.get_children_runs(parent_run_id)
            self.assertEqual(len(children), 1)
            self.assertEqual(children[0].run_id, child_run_id)
            self.assertEqual(children[0].parent_run_id, parent_run_id)
            self.assertEqual(children[0].user_input, "帮我查一下天气")
            self.assertEqual(children[0].reply, "子任务完成")
            self.assertEqual(MockAgent.call_args.kwargs["model_adapter"].model, "test-model")
            self.assertEqual(mock_instance.execute.call_args.kwargs["run_id"], child_run_id)
            MockVfsRegistry.create.assert_called_once_with(child_run_id)
            staged_vfs.commit_all.assert_called_once()
            MockPersistVfsRegistry.take.assert_called_once_with(child_run_id)
        finally:
            db.close()

    def test_child_run_failure_discards_vfs_and_does_not_persist_child_record(self):
        parent_run_id = "parent-run-fail"
        session_id = "session-with-model-fail"
        _seed_session_model(self.session_local, session_id)

        db = self.session_local()
        run_service = RunService(db)

        with (
            patch("agent_prototype.execution.child_run_launcher._executor", self.executor),
            patch("agent_prototype.execution.child_run_launcher._global_futures", self.futures),
            patch("agent_prototype.execution.child_run_launcher.AgentRunner") as MockAgent,
            patch("agent_prototype.execution.child_run_launcher.RunVfsRegistry") as MockVfsRegistry,
            patch(
                "agent_prototype.execution.child_run_launcher.SessionLocal", self.session_local
            ),
        ):
            mock_instance = MagicMock()
            mock_instance.execute.side_effect = RuntimeError("child failed")
            MockAgent.return_value = mock_instance

            registry = build_run_registry(
                child_dispatcher=run_service.child_dispatcher.create_launcher(
                    parent_run_id, session_id
                ),
                status_checker=run_service.child_dispatcher.create_status_checker(),
                child_waiter=run_service.child_dispatcher.create_waiter(),
            )
            result = registry.execute_tool_call(
                "spawn_child_agent",
                '{"task": "失败任务"}',
            )

            self.assertTrue(result.ok)
            child_run_id = result.content

            with self.assertRaises(RuntimeError):
                self.futures[child_run_id].result(timeout=10)

            MockVfsRegistry.create.assert_called_once_with(child_run_id)
            MockVfsRegistry.discard.assert_called_once_with(child_run_id)
            MockVfsRegistry.take.assert_not_called()

        try:
            run_store = RunTraceStore(db)
            children = run_store.get_children_runs(parent_run_id)
            self.assertEqual(children, [])
        finally:
            db.close()

    def test_multiple_children_all_link_to_same_parent(self):
        parent_run_id = "parent-run-multi"
        session_id = "session-with-model-multi"
        _seed_session_model(self.session_local, session_id)
        fake_output = build_run_output("完成")

        db = self.session_local()
        run_service = RunService(db)

        with (
            patch("agent_prototype.execution.child_run_launcher._executor", self.executor),
            patch("agent_prototype.execution.child_run_launcher._global_futures", self.futures),
            patch("agent_prototype.execution.child_run_launcher.AgentRunner") as MockAgent,
            patch(
                "agent_prototype.execution.child_run_launcher.SessionLocal", self.session_local
            ),
        ):

            mock_instance = MagicMock()
            mock_instance.execute.return_value = fake_output
            MockAgent.return_value = mock_instance

            registry = build_run_registry(
                child_dispatcher=run_service.child_dispatcher.create_launcher(
                    parent_run_id, session_id
                ),
                status_checker=run_service.child_dispatcher.create_status_checker(),
                child_waiter=run_service.child_dispatcher.create_waiter(),
            )
            r1 = registry.execute_tool_call("spawn_child_agent", '{"task": "任务一"}')
            r2 = registry.execute_tool_call("spawn_child_agent", '{"task": "任务二"}')

            self.futures[r1.content].result(timeout=10)
            self.futures[r2.content].result(timeout=10)

        try:
            run_store = RunTraceStore(db)
            children = run_store.get_children_runs(parent_run_id)
            self.assertEqual(len(children), 2)
            for child in children:
                self.assertEqual(child.parent_run_id, parent_run_id)
            self.assertEqual(MockAgent.call_args.kwargs["model_adapter"].model, "test-model")
        finally:
            db.close()


class TestGetChildrenRuns(unittest.TestCase):
    """get_children_runs 只返回指定 parent 的子 run，不混入其他 run。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine, self.session_local = make_sqlite_test_db(
            self.temp.name,
            "test_children.db",
        )

    def tearDown(self):
        self.engine.dispose()
        self.temp.cleanup()

    def test_children_isolated_from_other_parents(self):
        db = self.session_local()
        try:
            run_store = RunTraceStore(db)

            # parent A 有一个子 run
            run_store.create_child_run(
                parent_run_id="parent-A",
                session_id="session-A1",
                run_id="run-A1",
                agent_name="default",
                user_input="任务A",
                reply="结果A",
                events=[],
            )
            # parent B 有一个子 run
            run_store.create_child_run(
                parent_run_id="parent-B",
                session_id="session-B1",
                run_id="run-B1",
                agent_name="default",
                user_input="任务B",
                reply="结果B",
                events=[],
            )
            db.commit()

            children_of_a = run_store.get_children_runs("parent-A")
            self.assertEqual(len(children_of_a), 1)
            self.assertEqual(children_of_a[0].run_id, "run-A1")

            children_of_b = run_store.get_children_runs("parent-B")
            self.assertEqual(len(children_of_b), 1)
            self.assertEqual(children_of_b[0].run_id, "run-B1")

            # 不存在的 parent 返回空列表
            self.assertEqual(run_store.get_children_runs("parent-none"), [])
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
