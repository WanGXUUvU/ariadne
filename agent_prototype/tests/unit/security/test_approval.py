"""TASK-043 工具审批流程单测。

验证三条路径：
1. NEVER policy → 任何工具直接执行，不产生 approval_required 事件
2. UNTRUSTED policy + WRITE 工具 → 产生 approval_required 事件，不执行工具
3. ON_REQUEST policy + WRITE 工具 → 直接执行，不产生 approval_required 事件
"""

import asyncio
import unittest
from unittest.mock import MagicMock

from agent_prototype.tools.types import RiskLevel
from agent_prototype.core.types import ToolCall, ToolCallFunction
from agent_prototype.security.policy import ApprovalPolicy
from agent_prototype.security.approval.checker import needs_approval
from agent_prototype.execution.runtime.tool_runner import async_handle_tool_calls
from agent_prototype.tools.registry import ToolRegistry
from agent_prototype.tools.types import ToolDefinition


# ── 辅助：构造一个 fake ToolRegistry，只返回指定的 risk_level ──────────────


def make_registry(risk_level: RiskLevel) -> ToolRegistry:
    """构造只有一个 fake 工具的 ToolRegistry。"""
    registry = ToolRegistry()

    def fake_handler(**kwargs):
        return "ok"

    registry.register(
        ToolDefinition(
            name="fake_tool",
            schema={
                "name": "fake_tool",
                "description": "",
                "parameters": {"type": "object", "properties": {}},
            },
            handler=fake_handler,
            risk_level=risk_level,
        )
    )
    return registry


def make_tool_call(name: str = "fake_tool") -> ToolCall:
    return ToolCall(
        id="call_001",
        function=ToolCallFunction(name=name, arguments="{}"),
    )


async def collect_events(registry, tool_calls, policy, on_approval_required=None):
    """运行 async_handle_tool_calls，收集所有 AgentEvent，返回事件列表。"""
    from agent_prototype.execution.runtime.types import AgentEvent

    events = []
    async for item in async_handle_tool_calls(
        tool_registry=registry,
        tool_calls=tool_calls,
        allow_tool_names=None,
        event_index=0,
        session_id="mock_session",
        run_id="mock_run",
        approval_policy=policy,
        on_approval_required=on_approval_required,
    ):
        if isinstance(item, AgentEvent):
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


# ── async_handle_tool_calls 集成测试 ─────────────────────────────────────────


class TestAsyncHandleToolCallsApproval(unittest.TestCase):

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_never_policy_executes_write_tool_directly(self):
        """NEVER policy：WRITE 工具直接执行，不产生 approval_required 事件。"""
        registry = make_registry(RiskLevel.WRITE)
        events = self._run(collect_events(registry, [make_tool_call()], ApprovalPolicy.NEVER))
        types = [e.type for e in events]
        self.assertNotIn("approval_required", types)
        self.assertIn("tool_result", types)

    def test_untrusted_policy_blocks_write_tool(self):
        """UNTRUSTED policy：WRITE 工具被拦截，产生 approval_required，不产生 tool_result。"""
        registry = make_registry(RiskLevel.WRITE)
        events = self._run(collect_events(registry, [make_tool_call()], ApprovalPolicy.UNTRUSTED))
        types = [e.type for e in events]
        self.assertIn("approval_required", types)
        self.assertNotIn("tool_result", types)

    def test_on_request_policy_allows_write_tool(self):
        """ON_REQUEST policy：WRITE 工具直接执行，不产生 approval_required 事件。"""
        registry = make_registry(RiskLevel.WRITE)
        events = self._run(collect_events(registry, [make_tool_call()], ApprovalPolicy.ON_REQUEST))
        types = [e.type for e in events]
        self.assertNotIn("approval_required", types)
        self.assertIn("tool_result", types)

    def test_on_request_policy_blocks_danger_tool(self):
        """ON_REQUEST policy：DANGER 工具被拦截，产生 approval_required。"""
        registry = make_registry(RiskLevel.DANGER)
        events = self._run(collect_events(registry, [make_tool_call()], ApprovalPolicy.ON_REQUEST))
        types = [e.type for e in events]
        self.assertIn("approval_required", types)
        self.assertNotIn("tool_result", types)

    def test_on_approval_required_callback_called(self):
        """UNTRUSTED policy 拦截时，on_approval_required 回调被调用一次。"""
        registry = make_registry(RiskLevel.WRITE)
        callback = MagicMock(return_value="approval-123")
        self._run(
            collect_events(
                registry,
                [make_tool_call()],
                ApprovalPolicy.UNTRUSTED,
                on_approval_required=callback,
            )
        )
        callback.assert_called_once_with(
            "call_001",
            "fake_tool",
            "{}",
            None,
            0,
            "mock_run:step:0",
        )

    def test_approval_required_event_content_is_approval_id(self):
        """approval_required 事件的 content 包含回调返回的 approval_id。"""
        registry = make_registry(RiskLevel.WRITE)
        callback = MagicMock(return_value="approval-abc")
        events = self._run(
            collect_events(
                registry,
                [make_tool_call()],
                ApprovalPolicy.UNTRUSTED,
                on_approval_required=callback,
            )
        )
        approval_event = next(e for e in events if e.type == "approval_required")
        self.assertEqual(approval_event.content, "approval-abc")


if __name__ == "__main__":
    unittest.main()
