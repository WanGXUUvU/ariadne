"""测试 TASK-040b：并行子 Agent 调度（spawn / check / wait 三原语）。

覆盖：
1. spawn 立即返回 child_run_id，不阻塞
2. check_child_status 完成后返回 done + reply，未知 id 返回 not_found
3. wait_child_agent 阻塞等待，返回最终 reply；未知 id 返回 not_found 错误
4. 多个子 Agent 并行 spawn，全部完成
"""

_MOCK_PATH = "agent_prototype.execution.child_run_launcher.AgentRunner"
_BUILDER_MOCK_PATH = (
    "agent_prototype.execution.run_context_factory.RunContextFactory.create_adapter"
)

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

from agent_prototype.tools.registry import build_run_registry
from agent_prototype.execution.service import RunService
from agent_prototype.tests.helpers.db import make_sqlite_test_db
from agent_prototype.tests.helpers.factories import build_agent_output


class TestSpawnReturnsRunIdImmediately(unittest.TestCase):
    """spawn 不阻塞，立即返回 child_run_id 字符串。"""

    def setUp(self):
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.futures = {}
        self.builder_patcher = patch(_BUILDER_MOCK_PATH)
        self.mock_create_adapter = self.builder_patcher.start()
        self.mock_create_adapter.return_value = MagicMock()

        self.session_local_patcher = patch(
            "agent_prototype.execution.child_run_launcher.SessionLocal"
        )
        self.mock_session_local = self.session_local_patcher.start()
        self.mock_session_local.return_value = MagicMock()

    def tearDown(self):
        self.session_local_patcher.stop()
        self.builder_patcher.stop()
        self.executor.shutdown(wait=False)

    def test_spawn_returns_child_run_id(self):
        run_service = RunService(MagicMock())
        with (
            patch("agent_prototype.execution.child_run_launcher._executor", self.executor),
            patch("agent_prototype.execution.child_run_launcher._global_futures", self.futures),
            patch(_MOCK_PATH) as MockAgent,
        ):

            MockAgent.return_value.execute.return_value = build_agent_output("done")
            registry = build_run_registry(
                child_dispatcher=run_service.child_dispatcher.create_launcher(
                    "parent-1", "session-id"
                ),
                status_checker=run_service.child_dispatcher.create_status_checker(),
                child_waiter=run_service.child_dispatcher.create_waiter(),
            )
            result = registry.execute_tool_call("spawn_child_agent", '{"task": "task A"}')

        self.assertTrue(result.ok)
        child_run_id = result.content
        self.assertIsInstance(child_run_id, str)
        self.assertTrue(len(child_run_id) > 0)
        self.assertIn(child_run_id, self.futures)


class TestCheckChildStatus(unittest.TestCase):
    """check_child_status 正确反映子 Agent 的运行状态。"""

    def setUp(self):
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.futures = {}
        self.builder_patcher = patch(_BUILDER_MOCK_PATH)
        self.mock_create_adapter = self.builder_patcher.start()
        self.mock_create_adapter.return_value = MagicMock()

        self.session_local_patcher = patch(
            "agent_prototype.execution.child_run_launcher.SessionLocal"
        )
        self.mock_session_local = self.session_local_patcher.start()
        self.mock_session_local.return_value = MagicMock()

    def tearDown(self):
        self.session_local_patcher.stop()
        self.builder_patcher.stop()
        self.executor.shutdown(wait=False)

    def test_status_done_after_completion(self):
        run_service = RunService(MagicMock())
        with (
            patch("agent_prototype.execution.child_run_launcher._executor", self.executor),
            patch("agent_prototype.execution.child_run_launcher._global_futures", self.futures),
            patch(_MOCK_PATH) as MockAgent,
        ):

            MockAgent.return_value.execute.return_value = build_agent_output("结果X")
            registry = build_run_registry(
                child_dispatcher=run_service.child_dispatcher.create_launcher(
                    "parent-2", "session-id"
                ),
                status_checker=run_service.child_dispatcher.create_status_checker(),
                child_waiter=run_service.child_dispatcher.create_waiter(),
            )
            spawn_result = registry.execute_tool_call("spawn_child_agent", '{"task": "task B"}')
            child_run_id = spawn_result.content

            # 等待完成
            self.futures[child_run_id].result(timeout=10)

            check_result = registry.execute_tool_call(
                "check_child_status",
                json.dumps({"child_run_ids": json.dumps([child_run_id])}),
            )

        self.assertTrue(check_result.ok)
        statuses = json.loads(check_result.content)
        self.assertEqual(statuses[child_run_id]["status"], "done")
        self.assertEqual(statuses[child_run_id]["reply"], "结果X")

    def test_status_not_found_for_unknown_id(self):
        run_service = RunService(MagicMock())
        with (
            patch("agent_prototype.execution.child_run_launcher._executor", self.executor),
            patch("agent_prototype.execution.child_run_launcher._global_futures", self.futures),
        ):

            registry = build_run_registry(
                child_dispatcher=run_service.child_dispatcher.create_launcher(
                    "parent-3", "session-id"
                ),
                status_checker=run_service.child_dispatcher.create_status_checker(),
                child_waiter=run_service.child_dispatcher.create_waiter(),
            )
            result = registry.execute_tool_call(
                "check_child_status",
                json.dumps({"child_run_ids": json.dumps(["nonexistent-id"])}),
            )
        self.assertTrue(result.ok)
        statuses = json.loads(result.content)
        self.assertEqual(statuses["nonexistent-id"]["status"], "not_found")


class TestWaitChildAgent(unittest.TestCase):
    """wait_child_agent 阻塞等待并返回 reply。"""

    def setUp(self):
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.futures = {}
        self.builder_patcher = patch(_BUILDER_MOCK_PATH)
        self.mock_create_adapter = self.builder_patcher.start()
        self.mock_create_adapter.return_value = MagicMock()

        self.session_local_patcher = patch(
            "agent_prototype.execution.child_run_launcher.SessionLocal"
        )
        self.mock_session_local = self.session_local_patcher.start()
        self.mock_session_local.return_value = MagicMock()

    def tearDown(self):
        self.session_local_patcher.stop()
        self.builder_patcher.stop()
        self.executor.shutdown(wait=False)

    def test_wait_returns_reply(self):
        run_service = RunService(MagicMock())
        with (
            patch("agent_prototype.execution.child_run_launcher._executor", self.executor),
            patch("agent_prototype.execution.child_run_launcher._global_futures", self.futures),
            patch(_MOCK_PATH) as MockAgent,
        ):

            MockAgent.return_value.execute.return_value = build_agent_output("最终答案")
            registry = build_run_registry(
                child_dispatcher=run_service.child_dispatcher.create_launcher(
                    "parent-4", "session-id"
                ),
                status_checker=run_service.child_dispatcher.create_status_checker(),
                child_waiter=run_service.child_dispatcher.create_waiter(),
            )
            spawn_result = registry.execute_tool_call("spawn_child_agent", '{"task": "task C"}')
            child_run_id = spawn_result.content

            wait_result = registry.execute_tool_call(
                "wait_child_agent",
                json.dumps({"child_run_id": child_run_id}),
            )

        self.assertTrue(wait_result.ok)
        self.assertEqual(wait_result.content, "最终答案")

    def test_wait_not_found_returns_error(self):
        run_service = RunService(MagicMock())
        with (
            patch("agent_prototype.execution.child_run_launcher._executor", self.executor),
            patch("agent_prototype.execution.child_run_launcher._global_futures", self.futures),
        ):

            registry = build_run_registry(
                child_dispatcher=run_service.child_dispatcher.create_launcher(
                    "parent-5", "session-id"
                ),
                status_checker=run_service.child_dispatcher.create_status_checker(),
                child_waiter=run_service.child_dispatcher.create_waiter(),
            )
            result = registry.execute_tool_call(
                "wait_child_agent",
                json.dumps({"child_run_id": "no-such-id"}),
            )
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "not_found")


class TestParallelSpawn(unittest.TestCase):
    """多个子 Agent 并行 spawn，全部完成，结果互不干扰。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine, self.session_local = make_sqlite_test_db(
            self.temp.name,
            "test_parallel.db",
        )
        self.executor = ThreadPoolExecutor(max_workers=4)
        self.futures = {}
        self.builder_patcher = patch(_BUILDER_MOCK_PATH)
        self.mock_create_adapter = self.builder_patcher.start()
        self.mock_create_adapter.return_value = MagicMock()

    def tearDown(self):
        self.builder_patcher.stop()
        self.executor.shutdown(wait=False)
        self.engine.dispose()
        self.temp.cleanup()

    def test_three_parallel_children_all_complete(self):
        tasks = ["任务一", "任务二", "任务三"]
        child_run_ids = []

        run_service = RunService(MagicMock())
        with (
            patch("agent_prototype.execution.child_run_launcher._executor", self.executor),
            patch("agent_prototype.execution.child_run_launcher._global_futures", self.futures),
            patch(_MOCK_PATH) as MockAgent,
            patch(
                "agent_prototype.execution.child_run_launcher.SessionLocal", self.session_local
            ),
        ):

            MockAgent.return_value.execute.side_effect = [
                build_agent_output(f"结果{i}") for i in range(len(tasks))
            ]
            registry = build_run_registry(
                child_dispatcher=run_service.child_dispatcher.create_launcher(
                    "parent-parallel", "session-id"
                ),
                status_checker=run_service.child_dispatcher.create_status_checker(),
                child_waiter=run_service.child_dispatcher.create_waiter(),
            )
            for task in tasks:
                r = registry.execute_tool_call("spawn_child_agent", json.dumps({"task": task}))
                self.assertTrue(r.ok)
                child_run_ids.append(r.content)

            # 等待全部完成
            for cid in child_run_ids:
                self.futures[cid].result(timeout=10)

            # check 全部 done
            check_result = registry.execute_tool_call(
                "check_child_status",
                json.dumps({"child_run_ids": json.dumps(child_run_ids)}),
            )

        statuses = json.loads(check_result.content)
        self.assertEqual(len(statuses), 3)
        for cid in child_run_ids:
            self.assertEqual(statuses[cid]["status"], "done")


if __name__ == "__main__":
    unittest.main()
