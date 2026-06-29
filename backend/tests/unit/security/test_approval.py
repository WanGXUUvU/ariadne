"""TASK-043 工具审批流程单测。

验证三条路径：
1. NEVER policy → 任何工具直接执行，不产生 approval_required 事件
2. UNTRUSTED policy + WRITE 工具 → 产生 approval_required 事件，不执行工具
3. ON_REQUEST policy + WRITE 工具 → 直接执行，不产生 approval_required 事件
"""

import asyncio
import unittest

from backend.approval.checker import needs_approval
from backend.tools.types import RiskLevel
from backend.core.types import ToolCall, ToolCallFunction
from backend.security.policy import ApprovalPolicy
from backend.agent_loop.handle_tool_calls import stream_tool_calls
from backend.tools.registry import ToolRegistry
from backend.tools.result_types import ToolResult
from backend.tools.types import ToolDefinition

# ── 辅助：构造一个 fake ToolRegistry，只返回指定的 risk_level ──────────────


def make_registry(risk_level: RiskLevel) -> ToolRegistry:
    """构造只有一个 fake 工具的 ToolRegistry。"""
    registry = ToolRegistry()

    def fake_handler(**kwargs):
        return ToolResult(ok=True, content="ok")

    registry.register(
        ToolDefinition(
            name="fake_tool",
            schema={},
            handler=fake_handler,
            risk_level=risk_level,
        )
    )
    return registry


def make_mixed_registry() -> ToolRegistry:
    """构造一个包含 SAFE 工具和 WRITE 工具的 ToolRegistry。"""
    registry = ToolRegistry()

    def safe_handler(**k):
        return ToolResult(ok=True, content="safe-ok")
    def write_handler(**k):
        return ToolResult(ok=True, content="write-ok")
    registry.register(
        ToolDefinition(
            name="safe_tool",
            schema={},
            handler=safe_handler,
            risk_level=RiskLevel.SAFE,
        )
    )
    registry.register(
        ToolDefinition(
            name="write_tool",
            schema={},
            handler=write_handler,
            risk_level=RiskLevel.WRITE,
        )
    )
    return registry


def make_tool_call(name: str = "fake_tool", tool_call_id: str = "call_001") -> ToolCall:
    return ToolCall(
        id=tool_call_id,
        function=ToolCallFunction(name=name, arguments="{}"),
    )


async def collect_events(registry, tool_calls, policy):
    """运行 stream_tool_calls，收集所有 RunEvent，返回事件列表。"""
    from backend.agent_loop.types import RunEvent

    events = []
    async for item in stream_tool_calls(
        tool_registry=registry,
        tool_calls=tool_calls,
        allow_tool_names=None,
        event_index=0,
        session_id="mock_session",
        run_id="mock_run",
        approval_policy=policy,
    ):
        if isinstance(item, RunEvent):
            events.append(item)
    return events


# ── needs_approval 单元测试 ──────────────────────────────────────────────────


class TestNeedsApproval(unittest.TestCase):

    def test_never_always_false(self):
        for risk in RiskLevel:
            self.assertFalse(needs_approval(ApprovalPolicy.NEVER, risk))

    def test_untrusted_blocks_write_and_danger(self):
        self.assertTrue(needs_approval(ApprovalPolicy.UNTRUSTED, RiskLevel.WRITE))
        self.assertTrue(needs_approval(ApprovalPolicy.UNTRUSTED, RiskLevel.DANGER))

    def test_untrusted_allows_safe(self):
        self.assertFalse(needs_approval(ApprovalPolicy.UNTRUSTED, RiskLevel.SAFE))

    def test_on_request_only_blocks_danger(self):
        self.assertFalse(needs_approval(ApprovalPolicy.ON_REQUEST, RiskLevel.WRITE))
        self.assertFalse(needs_approval(ApprovalPolicy.ON_REQUEST, RiskLevel.SAFE))
        self.assertTrue(needs_approval(ApprovalPolicy.ON_REQUEST, RiskLevel.DANGER))


# ── stream_tool_calls 集成测试 ─────────────────────────────────────────


class TestAsyncHandleToolCallsApproval(unittest.TestCase):

    def _run(self, coro):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)

    def test_never_policy_executes_write_tool_directly(self):
        """NEVER policy：WRITE 工具直接执行，不产生 approval_required 事件。"""
        registry = make_registry(RiskLevel.WRITE)
        events = self._run(
            collect_events(registry, [make_tool_call()], ApprovalPolicy.NEVER)
        )
        types = [e.type for e in events]
        self.assertIn("tool_result", types)
        self.assertNotIn("approval_required", types)

    def test_untrusted_policy_blocks_write_tool(self):
        """UNTRUSTED policy：WRITE 工具被拦截，产生 approval_required，不产生 tool_result。"""
        registry = make_registry(RiskLevel.WRITE)
        events = self._run(
            collect_events(registry, [make_tool_call()], ApprovalPolicy.UNTRUSTED)
        )
        types = [e.type for e in events]
        self.assertIn("approval_required", types)
        self.assertNotIn("tool_result", types)

    def test_on_request_policy_allows_write_tool(self):
        """ON_REQUEST policy：WRITE 工具直接执行，不产生 approval_required 事件。"""
        registry = make_registry(RiskLevel.WRITE)
        events = self._run(
            collect_events(registry, [make_tool_call()], ApprovalPolicy.ON_REQUEST)
        )
        types = [e.type for e in events]
        self.assertIn("tool_result", types)
        self.assertNotIn("approval_required", types)

    def test_on_request_policy_blocks_danger_tool(self):
        """ON_REQUEST policy：DANGER 工具被拦截，产生 approval_required。"""
        registry = make_registry(RiskLevel.DANGER)
        events = self._run(
            collect_events(registry, [make_tool_call()], ApprovalPolicy.ON_REQUEST)
        )
        types = [e.type for e in events]
        self.assertIn("approval_required", types)
        self.assertNotIn("tool_result", types)

    def test_approval_required_event_content_is_arguments(self):
        """approval_required 事件的 content 包含 arguments。"""
        registry = make_registry(RiskLevel.WRITE)
        events = self._run(
            collect_events(registry, [make_tool_call()], ApprovalPolicy.UNTRUSTED)
        )
        approval_event = next(e for e in events if e.type == "approval_required")
        self.assertEqual(approval_event.content, "{}")

    def test_mixed_ready_and_pending_approval_yields_ready_result(self):
        """同批次含 ready + pending 时，已完成 ready 工具结果应该被正确产生并放入消息暂存。"""
        registry = make_mixed_registry()
        events = []
        tool_batch_result = None

        async def run():
            nonlocal tool_batch_result
            async for item in stream_tool_calls(
                tool_registry=registry,
                tool_calls=[
                    make_tool_call("safe_tool", "call_safe"),
                    make_tool_call("write_tool", "call_write"),
                ],
                allow_tool_names=None,
                event_index=0,
                session_id="mock_session",
                run_id="mock_run",
                approval_policy=ApprovalPolicy.UNTRUSTED,
            ):
                from backend.agent_loop.types import RunEvent, ToolBatchResult
                if isinstance(item, RunEvent):
                    events.append(item)
                elif isinstance(item, ToolBatchResult):
                    tool_batch_result = item

        self._run(run())

        # 验证 ready_tool (safe_tool) 被执行并有 tool_result，但 pending_tool (write_tool) 被拦截
        self.assertEqual(
            [event.type for event in events],
            [
                "assistant_tool_call",
                "assistant_tool_call",
                "tool_result",
                "approval_required",
            ],
        )

        self.assertIsNotNone(tool_batch_result)
        self.assertTrue(tool_batch_result.paused_for_approval)
        self.assertEqual(len(tool_batch_result.tool_messages), 1)
        self.assertEqual(tool_batch_result.tool_messages[0].tool_call_id, "call_safe")
        self.assertEqual(tool_batch_result.tool_messages[0].content, "safe-ok")


if __name__ == "__main__":
    unittest.main()
