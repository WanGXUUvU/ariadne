import json
import unittest
from typing import Any, Awaitable, Callable

from agent_prototype.tools.result_types import ToolResult, ToolError
from agent_prototype.security.middleware.base import (
    BaseMiddleware,
    MiddlewarePipeline,
    ToolCallContext,
)
from agent_prototype.security.sandbox.middleware import SandboxMiddleware


class DummyMiddleware(BaseMiddleware):
    """测试专用的哑中间件，记录执行轨迹。"""

    def __init__(self, name: str, trace_list: list[str], short_circuit: bool = False):
        self.name = name
        self.trace_list = trace_list
        self.short_circuit = short_circuit

    async def call(
        self,
        context: Any,
        next_call: Callable[[], Awaitable[Any]],
    ) -> Any:
        self.trace_list.append(f"enter:{self.name}")

        if isinstance(context, ToolCallContext):
            setattr(context, f"passed_{self.name}", True)

        if self.short_circuit:
            self.trace_list.append(f"short_circuit:{self.name}")
            return ToolResult(
                ok=False,
                content=None,
                error=ToolError(
                    code="SHORT_CIRCUIT",
                    tool_name=(
                        context.tool_name
                        if hasattr(context, "tool_name")
                        else "unknown"
                    ),
                    message=f"Short circuited by {self.name}",
                ),
            )

        res = await next_call()
        self.trace_list.append(f"exit:{self.name}")
        return res


class CrashingMiddleware(BaseMiddleware):
    """崩溃中间件，验证异常隔离。"""

    async def call(
        self,
        context: Any,
        next_call: Callable[[], Awaitable[Any]],
    ) -> Any:
        raise RuntimeError("Middleware crashed on purpose")


class TestGeneralMiddleware(unittest.IsolatedAsyncioTestCase):
    """通用洋葱圈中间件管道单元测试。"""

    def setUp(self):
        self.context = ToolCallContext(
            tool_name="test_tool",
            tool_args='{"arg": 1}',
            tool_call_id="call_123",
            session_id="session_abc",
        )
        self.trace: list[str] = []

    async def test_pipeline_onion_ring_order(self):
        """测试中间件洋葱圈式进出执行顺序。"""
        m1 = DummyMiddleware("outer", self.trace)
        m2 = DummyMiddleware("inner", self.trace)
        pipeline = MiddlewarePipeline([m1, m2])

        async def terminal():
            self.trace.append("terminal")
            return ToolResult(ok=True, content="terminal_ok")

        result = await pipeline.execute(self.context, terminal)

        self.assertTrue(result.ok)
        self.assertEqual(result.content, "terminal_ok")

        expected_trace = [
            "enter:outer",
            "enter:inner",
            "terminal",
            "exit:inner",
            "exit:outer",
        ]
        self.assertEqual(self.trace, expected_trace)
        self.assertTrue(getattr(self.context, "passed_outer"))
        self.assertTrue(getattr(self.context, "passed_inner"))

    async def test_pipeline_short_circuit(self):
        """测试中间件短路保护（不调用 next_call）。"""
        m1 = DummyMiddleware("outer", self.trace)
        m2 = DummyMiddleware("inner", self.trace, short_circuit=True)
        m3 = DummyMiddleware("innermost", self.trace)
        pipeline = MiddlewarePipeline([m1, m2, m3])

        async def terminal():
            self.trace.append("terminal")
            return ToolResult(ok=True, content="terminal_ok")

        result = await pipeline.execute(self.context, terminal)

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "SHORT_CIRCUIT")

        expected_trace = [
            "enter:outer",
            "enter:inner",
            "short_circuit:inner",
            "exit:outer",
        ]
        self.assertEqual(self.trace, expected_trace)

    async def test_pipeline_exception_handling(self):
        """测试中间件崩溃时，管道能优雅隔离并向上抛出异常。"""
        m1 = DummyMiddleware("outer", self.trace)
        m2 = CrashingMiddleware()
        pipeline = MiddlewarePipeline([m1, m2])

        async def terminal():
            return ToolResult(ok=True, content="terminal_ok")

        with self.assertRaises(RuntimeError) as ctx:
            await pipeline.execute(self.context, terminal)

        self.assertEqual(str(ctx.exception), "Middleware crashed on purpose")

    async def test_sandbox_relative_path_passthrough(self):
        """测试 SandboxMiddleware 不再改写相对路径参数。"""
        sandbox = SandboxMiddleware()
        context = ToolCallContext(
            tool_name="write_file",
            tool_args='{"path": "src/App.vue", "content": "<template></template>"}',
            tool_call_id="call_456",
            session_id="session_xyz",
            workspace_path="/fake/workspace/root",
        )

        async def terminal():
            args = json.loads(context.tool_args)
            self.assertEqual(args["path"], "src/App.vue")
            return ToolResult(ok=True, content="ok")

        pipeline = MiddlewarePipeline([sandbox])
        result = await pipeline.execute(context, terminal)
        self.assertTrue(result.ok)

    async def test_sandbox_absolute_path_passthrough(self):
        """测试 SandboxMiddleware 不再改写绝对路径参数。"""
        sandbox = SandboxMiddleware()
        context = ToolCallContext(
            tool_name="read_file",
            tool_args='{"path": "/package.json"}',
            tool_call_id="call_789",
            session_id="session_xyz",
            workspace_path="/fake/workspace/root",
        )

        async def terminal():
            args = json.loads(context.tool_args)
            self.assertEqual(args["path"], "/package.json")
            return ToolResult(ok=True, content="ok")

        pipeline = MiddlewarePipeline([sandbox])
        result = await pipeline.execute(context, terminal)
        self.assertTrue(result.ok)

    async def test_sandbox_tool_not_allowed_blocks(self):
        """测试 SandboxMiddleware 对不在 allow_tool_names 白名单里的工具执行优雅拦截。"""
        sandbox = SandboxMiddleware()
        context = ToolCallContext(
            tool_name="unauthorized_tool",
            tool_args="{}",
            tool_call_id="call_999",
            session_id="session_xyz",
            allow_tool_names=["write_file", "read_file"],
        )

        async def terminal():
            self.fail("Terminal should not be called due to tool restriction")

        pipeline = MiddlewarePipeline([sandbox])
        result = await pipeline.execute(context, terminal)

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code, "TOOL_NOT_ALLOWED")
