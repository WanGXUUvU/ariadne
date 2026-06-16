"""工具调用管道集成测试。

覆盖：工具调用从 ToolRegistry.execute_tool_call → MiddlewarePipeline 全链路行为。
不依赖真实 LLM，所有工具均为内联 stub。
"""

import json
import unittest

from agent_prototype.tools.types import RiskLevel
from agent_prototype.security.middleware.base import (
    BaseMiddleware,
    MiddlewarePipeline,
    ToolCallContext,
)
from agent_prototype.tools.types import ToolDefinition
from agent_prototype.tools.registry import ToolRegistry
from agent_prototype.tools.result_types import ToolResult, ToolError

# ── Stub 工具 ──────────────────────────────────────────────────────────────────


def _safe_handler(message: str = "hello") -> ToolResult:
    return ToolResult(ok=True, content=f"echo:{message}")


def _danger_handler(path: str = "/tmp") -> ToolResult:
    return ToolResult(ok=True, content=f"deleted:{path}")


def _failing_handler() -> ToolResult:
    return ToolResult(
        ok=False,
        error=ToolError(code="FAIL", tool_name="failing_tool", message="always fails"),
    )


# ── 哑中间件 ──────────────────────────────────────────────────────────────────


class TraceMiddleware(BaseMiddleware):
    """记录每次经过的工具名，用于断言执行顺序。"""

    def __init__(self, log: list[str]):
        self.log = log

    async def call(self, context, next_call):
        self.log.append(f"before:{context.tool_name}")
        result = await next_call()
        self.log.append(f"after:{context.tool_name}")
        return result


class BlockDangerMiddleware(BaseMiddleware):
    """拦截 risk_level == DANGER 的调用，模拟审批拒绝。"""

    async def call(self, context: ToolCallContext, next_call):
        if context.tool_name == "danger_tool":
            return ToolResult(
                ok=False,
                error=ToolError(
                    code="BLOCKED",
                    tool_name=context.tool_name,
                    message="Dangerous tool blocked by policy",
                ),
            )
        return await next_call()


# ── 测试类 ────────────────────────────────────────────────────────────────────


class TestToolPipeline(unittest.IsolatedAsyncioTestCase):
    """工具调用管道行为测试。"""

    def setUp(self):
        safe_schema = {
            "type": "function",
            "function": {
                "name": "safe_tool",
                "description": "a safe tool",
                "parameters": {
                    "type": "object",
                    "properties": {"message": {"type": "string"}},
                },
            },
        }
        danger_schema = {
            "type": "function",
            "function": {
                "name": "danger_tool",
                "description": "a dangerous tool",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                },
            },
        }
        fail_schema = {
            "type": "function",
            "function": {
                "name": "failing_tool",
                "description": "always fails",
                "parameters": {"type": "object", "properties": {}},
            },
        }

        self.registry = ToolRegistry()
        self.registry.register(
            ToolDefinition(
                name="safe_tool",
                schema=safe_schema,
                handler=_safe_handler,
                risk_level=RiskLevel.SAFE,
            )
        )
        self.registry.register(
            ToolDefinition(
                name="danger_tool",
                schema=danger_schema,
                handler=_danger_handler,
                risk_level=RiskLevel.DANGER,
            )
        )
        self.registry.register(
            ToolDefinition(
                name="failing_tool",
                schema=fail_schema,
                handler=_failing_handler,
                risk_level=RiskLevel.SAFE,
            )
        )

    # ── 直接执行（不经过管道）─────────────────────────────────────────────────

    def test_registry_executes_safe_tool(self):
        result = self.registry.execute_tool_call(
            "safe_tool", json.dumps({"message": "world"})
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.content, "echo:world")

    def test_registry_returns_error_on_failing_tool(self):
        result = self.registry.execute_tool_call("failing_tool", "{}")
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "FAIL")

    def test_registry_returns_error_for_unknown_tool(self):
        result = self.registry.execute_tool_call("nonexistent_tool", "{}")
        self.assertFalse(result.ok)

    # ── 管道执行 ──────────────────────────────────────────────────────────────

    async def _run_pipeline(
        self, tool_name: str, args: dict, middlewares
    ) -> ToolResult:
        """辅助：构建 context + pipeline，执行并返回结果。"""
        context = ToolCallContext(
            tool_name=tool_name,
            tool_args=json.dumps(args),
            tool_call_id="call_test",
            session_id="session_test",
        )
        pipeline = MiddlewarePipeline(middlewares)

        async def terminal():
            return self.registry.execute_tool_call(tool_name, json.dumps(args))

        return await pipeline.execute(context, terminal)

    async def test_pipeline_passes_through_safe_tool(self):
        """安全工具能透过中间件管道正常执行。"""
        log: list[str] = []
        result = await self._run_pipeline(
            "safe_tool", {"message": "pipe"}, [TraceMiddleware(log)]
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.content, "echo:pipe")
        self.assertEqual(log, ["before:safe_tool", "after:safe_tool"])

    async def test_pipeline_blocks_dangerous_tool(self):
        """危险工具被 BlockDangerMiddleware 拦截，不到达 terminal。"""
        result = await self._run_pipeline(
            "danger_tool", {"path": "/etc"}, [BlockDangerMiddleware()]
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "BLOCKED")

    async def test_pipeline_onion_order_with_multiple_middleware(self):
        """多层中间件洋葱圈顺序：outer → inner → terminal → inner → outer。"""
        log: list[str] = []

        # 覆盖名字区分 outer / inner
        async def outer_call(ctx, nxt):
            log.append("enter:outer")
            r = await nxt()
            log.append("exit:outer")
            return r

        async def inner_call(ctx, nxt):
            log.append("enter:inner")
            r = await nxt()
            log.append("exit:inner")
            return r

        class NamedMiddleware(BaseMiddleware):
            def __init__(self, fn):
                self._fn = fn

            async def call(self, ctx, nxt):
                return await self._fn(ctx, nxt)

        pipeline = MiddlewarePipeline(
            [NamedMiddleware(outer_call), NamedMiddleware(inner_call)]
        )

        async def terminal():
            log.append("terminal")
            return ToolResult(ok=True, content="ok")

        context = ToolCallContext(
            tool_name="safe_tool", tool_args="{}", tool_call_id="x", session_id="s"
        )
        await pipeline.execute(context, terminal)
        self.assertEqual(
            log, ["enter:outer", "enter:inner", "terminal", "exit:inner", "exit:outer"]
        )

    async def test_empty_pipeline_goes_straight_to_terminal(self):
        """空管道直接执行 terminal。"""
        result = await self._run_pipeline("safe_tool", {"message": "direct"}, [])
        self.assertTrue(result.ok)
        self.assertEqual(result.content, "echo:direct")
