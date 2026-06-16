import unittest

from agent_prototype.agent.types import AgentDefinition
from agent_prototype.execution.persistence.types import RunInput
from agent_prototype.core.types import StreamChunk, ToolCall, ToolCallFunction
from agent_prototype.execution.runtime.agent_runner import AgentRunner
from agent_prototype.tests.helpers.factories import build_assistant_response


class FakeModelAdapter:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate(self, request):
        self.calls.append(request)
        return self.responses.pop(0)


class FakeAsyncStreamAdapter:
    def __init__(self, leadin_chunks):
        self.leadin_chunks = list(leadin_chunks)
        self.calls = []

    async def async_stream_generate(self, request):
        self.calls.append(request)
        if len(self.calls) == 1:
            for chunk in self.leadin_chunks:
                yield StreamChunk(type="content_delta", content_delta=chunk)
            yield _tool_call_chunk()
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
