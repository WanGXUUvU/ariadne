import unittest

from backend.agent.types import AgentDefinition
from backend.execution.persistence.types import RunContext, RunInput
from backend.core.types import ModelUsage, StreamChunk, ToolCall, ToolCallFunction
from backend.execution.runtime.agent_runner import AgentRunner
from backend.execution.runtime.run_lifecycle import (
    RunLifecycle,
    RunLifecycleParams,
    UsageItem,
)
from backend.tests.helpers.factories import build_assistant_response
from backend.security.policy.types import ApprovalPolicy


class FakeModelAdapter:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate(self, request):
        self.calls.append(request)
        return self.responses.pop(0)


class FakeAsyncStreamAdapter:
    def __init__(self, leadin_chunks, usages=None):
        self.leadin_chunks = list(leadin_chunks)
        self.usages = list(usages or [])
        self.calls = []

    async def async_stream_generate(self, request):
        self.calls.append(request)
        if len(self.calls) == 1:
            for chunk in self.leadin_chunks:
                yield StreamChunk(type="content_delta", content_delta=chunk)
            yield _tool_call_chunk()
            yield StreamChunk(
                type="done",
                finish_reason="tool_calls",
                usage=self.usages[0] if self.usages else None,
            )
            return

        yield StreamChunk(type="content_delta", content_delta="final reply")
        yield StreamChunk(
            type="done",
            finish_reason="stop",
            usage=self.usages[1] if len(self.usages) > 1 else None,
        )


class FakeMultiDeltaAsyncStreamAdapter:
    def __init__(self):
        self.calls = []

    async def async_stream_generate(self, request):
        self.calls.append(request)
        if len(self.calls) == 1:
            yield StreamChunk(
                type="tool_call_delta",
                tool_call_delta={
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "call_001",
                            "function": {"name": "echo_", "arguments": ""},
                        }
                    ]
                },
            )
            yield StreamChunk(
                type="tool_call_delta",
                tool_call_delta={
                    "tool_calls": [
                        {
                            "index": 0,
                            "function": {"name": "tool", "arguments": '{"text"'},
                        }
                    ]
                },
            )
            yield StreamChunk(
                type="tool_call_delta",
                tool_call_delta={
                    "tool_calls": [
                        {
                            "index": 0,
                            "function": {"arguments": ': "hello"}'},
                        }
                    ]
                },
            )
            yield StreamChunk(type="done", finish_reason="tool_calls")
            return

        yield StreamChunk(type="content_delta", content_delta="final reply")
        yield StreamChunk(type="done", finish_reason="stop")


def _tool_call_chunk():
    return StreamChunk(
        type="tool_call_delta",
        finish_reason="tool_calls",
        tool_call_delta={
            "tool_calls": [
                {
                    "index": 0,
                    "id": "call_001",
                    "function": {
                        "name": "echo_tool",
                        "arguments": '{"text": "hello"}',
                    },
                }
            ]
        },
    )


def _agent_for_echo(model_adapter):
    return AgentRunner(
        agent_profile=AgentDefinition(
            id="default",
            name="Default Agent",
            system_prompt="你是一个助手",
            description=None,
            tool_names=["echo_tool"],
        ),
        model_adapter=model_adapter,
    )


class FakeRecorder:
    def __init__(self):
        self.finalizations = []

    def finalize_run(self, finalization):
        self.finalizations.append(finalization)


class TestAgent(unittest.TestCase):
    def test_run_uses_definition_system_prompt(self):
        custom_definition = AgentDefinition(
            id="default",
            name="Default Agent",
            system_prompt="你是一个严格的代码审查助手",
            description="test definition",
            tool_names=[],
        )
        fake_adapter = FakeModelAdapter(
            [
                build_assistant_response(content="mock reply"),
            ]
        )

        agent = AgentRunner(agent_profile=custom_definition, model_adapter=fake_adapter)
        output = agent.execute(RunInput(session_id="session-a", user_input="你好"))

        self.assertEqual(output.reply, "mock reply")
        request = fake_adapter.calls[0]
        self.assertEqual(request.messages[0].role, "system")
        self.assertEqual(request.messages[0].content, "你是一个严格的代码审查助手")

    def test_run_updates_state_and_returns_reply(self):
        fake_adapter = FakeModelAdapter(
            [
                build_assistant_response(content="mock reply"),
            ]
        )

        agent = AgentRunner(model_adapter=fake_adapter)
        output = agent.execute(RunInput(session_id="session-a", user_input="你好"))

        self.assertEqual(output.reply, "mock reply")
        self.assertEqual(output.state.step, 1)
        self.assertEqual(output.state.messages[-1].role, "assistant")
        self.assertEqual(output.state.messages[-1].content, "mock reply")
        self.assertEqual(len(fake_adapter.calls), 1)

    def test_run_handles_tool_call_then_returns_final_reply(self):
        fake_adapter = FakeModelAdapter(
            [
                build_assistant_response(
                    content=None,
                    tool_calls=[
                        ToolCall(
                            id="call_001",
                            function=ToolCallFunction(
                                name="echo_tool",
                                arguments='{"text": "hello"}',
                            ),
                        )
                    ],
                ),
                build_assistant_response(content="final reply"),
            ]
        )

        agent = AgentRunner(model_adapter=fake_adapter)
        output = agent.execute(
            RunInput(session_id="session-a", user_input="帮我测试工具")
        )

        self.assertEqual(output.reply, "final reply")
        self.assertEqual(len(fake_adapter.calls), 2)
        self.assertEqual(fake_adapter.calls[0].messages[0].role, "system")
        self.assertEqual(fake_adapter.calls[1].messages[-1].role, "tool")

    def test_run_records_tool_error_trace(self):
        fake_adapter = FakeModelAdapter(
            [
                build_assistant_response(
                    content=None,
                    tool_calls=[
                        ToolCall(
                            id="call_001",
                            function=ToolCallFunction(
                                name="write_file",
                                arguments='{"path": "/tmp", "content": "hello"}',
                            ),
                        )
                    ],
                ),
                build_assistant_response(content="final reply after error"),
            ]
        )

        agent = AgentRunner(model_adapter=fake_adapter)
        output = agent.execute(
            RunInput(session_id="session-a", user_input="帮我测试错误 trace")
        )

        self.assertEqual(output.reply, "final reply after error")
        self.assertEqual(len(fake_adapter.calls), 2)
        self.assertEqual(output.events[1].type, "tool_error")

    def test_run_rejects_disallowed_tool_call(self):
        fake_adapter = FakeModelAdapter(
            [
                build_assistant_response(
                    content=None,
                    tool_calls=[
                        ToolCall(
                            id="call_001",
                            function=ToolCallFunction(
                                name="write_file",
                                arguments='{"path": "demo.txt", "content": "hello"}',
                            ),
                        )
                    ],
                )
            ]
        )

        agent = AgentRunner(
            agent_profile=AgentDefinition(
                id="default",
                name="Default Agent",
                system_prompt="你是一个助手",
                description=None,
                tool_names=["echo_tool"],
            ),
            model_adapter=fake_adapter,
        )

        with self.assertRaises(ValueError) as ctx:
            agent.execute(RunInput(session_id="session-a", user_input="帮我测试权限"))

        self.assertIn("Tool not allowed: write_file", str(ctx.exception))
        self.assertEqual(len(fake_adapter.calls), 1)


class TestAsyncAgent(unittest.IsolatedAsyncioTestCase):
    async def test_async_stream_run_preserves_tool_call_leadin_in_state(self):
        fake_adapter = FakeAsyncStreamAdapter(["好的，让我", "帮你搜一下"])
        agent = _agent_for_echo(fake_adapter)

        async for _ in agent.async_stream_run(
            RunInput(session_id="session-a", user_input="帮我测试工具")
        ):
            pass

        tool_call_message = agent.state.messages[1]
        self.assertEqual(tool_call_message.role, "assistant")
        self.assertEqual(tool_call_message.content, "好的，让我帮你搜一下")
        self.assertEqual(tool_call_message.tool_calls[0].function.name, "echo_tool")
        self.assertEqual(
            fake_adapter.calls[1].messages[2].content,
            "好的，让我帮你搜一下",
        )

    async def test_async_stream_run_omits_empty_tool_call_leadin_content(self):
        fake_adapter = FakeAsyncStreamAdapter([])
        agent = _agent_for_echo(fake_adapter)

        async for _ in agent.async_stream_run(
            RunInput(session_id="session-a", user_input="帮我测试工具")
        ):
            pass

        tool_call_message = agent.state.messages[1]
        self.assertEqual(tool_call_message.role, "assistant")
        self.assertIsNone(tool_call_message.content)
        self.assertEqual(tool_call_message.tool_calls[0].function.name, "echo_tool")
        self.assertIsNone(fake_adapter.calls[1].messages[2].content)

    async def test_lifecycle_yields_usage_for_each_model_call(self):
        fake_adapter = FakeAsyncStreamAdapter(
            [],
            usages=[
                ModelUsage(input_tokens=100, output_tokens=20, total_tokens=120),
                ModelUsage(input_tokens=150, output_tokens=30, total_tokens=180),
            ],
        )
        agent = _agent_for_echo(fake_adapter)
        recorder = FakeRecorder()
        ctx = RunContext(
            state=agent.state,
            agent_profile=agent.agent_profile,
            adapter=fake_adapter,
            approval_policy=ApprovalPolicy.NEVER,
            effective_agent_name="Default Agent",
            workspace_path="",
            session_type="coding",
        )
        lifecycle = RunLifecycle(
            RunLifecycleParams(
                ctx=ctx,
                agent_runner=agent,
                recorder=recorder,
                run_input=RunInput(session_id="session-a", user_input="帮我测试工具"),
                run_id="run-a",
            )
        )

        usage_items = []
        async for item in lifecycle.iterate():
            if isinstance(item, UsageItem):
                usage_items.append(item)

        self.assertEqual([item.model_call_index for item in usage_items], [1, 2])
        self.assertEqual(usage_items[0].usage.output_tokens, 20)
        self.assertEqual(usage_items[0].usage.total_tokens, 120)
        self.assertEqual(usage_items[1].usage.input_tokens, 150)
        self.assertEqual(usage_items[1].usage.output_tokens, 30)
        self.assertEqual(usage_items[1].usage.total_tokens, 180)
        self.assertEqual(recorder.finalizations[0].usage.input_tokens, 150)

    async def test_lifecycle_does_not_persist_transient_tool_call_deltas(self):
        fake_adapter = FakeMultiDeltaAsyncStreamAdapter()
        agent = _agent_for_echo(fake_adapter)
        recorder = FakeRecorder()
        ctx = RunContext(
            state=agent.state,
            agent_profile=agent.agent_profile,
            adapter=fake_adapter,
            approval_policy=ApprovalPolicy.NEVER,
            effective_agent_name="Default Agent",
            workspace_path="",
            session_type="coding",
        )
        lifecycle = RunLifecycle(
            RunLifecycleParams(
                ctx=ctx,
                agent_runner=agent,
                recorder=recorder,
                run_input=RunInput(session_id="session-a", user_input="帮我测试工具"),
                run_id="run-a",
            )
        )

        live_tool_call_events = []
        async for item in lifecycle.iterate():
            if getattr(item, "type", None) == "run_event" and item.event.type == "assistant_tool_call":
                live_tool_call_events.append(item.event)

        persisted_tool_call_events = [
            event
            for event in recorder.finalizations[0].events
            if event.type == "assistant_tool_call"
        ]
        self.assertGreater(len(live_tool_call_events), 1)
        self.assertEqual(len(persisted_tool_call_events), 1)
        self.assertFalse(persisted_tool_call_events[0].transient)
        self.assertEqual(persisted_tool_call_events[0].content, '{"text": "hello"}')
