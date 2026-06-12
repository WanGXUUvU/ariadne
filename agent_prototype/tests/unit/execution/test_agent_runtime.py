import unittest

from agent_prototype.agent.types import AgentDefinition
from agent_prototype.execution.persistence.types import AgentInput
from agent_prototype.core.types import ToolCall, ToolCallFunction
from agent_prototype.execution.runtime.agent_runtime import AgentRunner
from agent_prototype.tests.helpers.factories import build_assistant_response


class FakeModelAdapter:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def generate(self, request):
        self.calls.append(request)
        return self.responses.pop(0)


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
        output = agent.execute(AgentInput(session_id="session-a", user_input="你好"))

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
        output = agent.execute(AgentInput(session_id="session-a", user_input="你好"))

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
        output = agent.execute(AgentInput(session_id="session-a", user_input="帮我测试工具"))

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
        output = agent.execute(AgentInput(session_id="session-a", user_input="帮我测试错误 trace"))

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
            agent.execute(AgentInput(session_id="session-a", user_input="帮我测试权限"))

        self.assertIn("Tool not allowed: write_file", str(ctx.exception))
        self.assertEqual(len(fake_adapter.calls), 1)
