import unittest
from unittest.mock import patch

from agent_prototype.core.agent_definition import AgentDefinition
from agent_prototype.core.schemas import AgentInput
from agent_prototype.runtime.agent_runtime import Agent


class TestAgent(unittest.TestCase):
    @patch("agent_prototype.runtime.agent_runtime.call_llm", return_value={"role": "assistant", "content": "mock reply"})
    def test_run_uses_definition_system_prompt(self, mock_call_llm):
        custom_definition = AgentDefinition(
            id="default",
            name="Default Agent",
            system_prompt="你是一个严格的代码审查助手",
            description="test definition",
            tool_names=[],
        )

        agent = Agent(definition=custom_definition)
        output = agent.run(AgentInput(session_id="session-a", user_input="你好"))

        self.assertEqual(output.reply, "mock reply")
        messages = mock_call_llm.call_args.args[0]
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[0]["content"], "你是一个严格的代码审查助手")

    @patch("agent_prototype.runtime.agent_runtime.call_llm", return_value={"role": "assistant", "content": "mock reply"})
    def test_run_updates_state_and_returns_reply(self, mock_call_llm):
        agent = Agent()
        output = agent.run(AgentInput(session_id="session-a", user_input="你好"))

        self.assertEqual(output.reply, "mock reply")
        self.assertEqual(output.state.step, 1)
        self.assertEqual([m.model_dump(exclude_none=True) for m in output.state.messages][-1]["content"], "mock reply")
        mock_call_llm.assert_called_once()

    @patch(
        "agent_prototype.runtime.agent_runtime.call_llm",
        side_effect=[
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_001",
                        "type": "function",
                        "function": {
                            "name": "echo_tool",
                            "arguments": "{\"text\": \"hello\"}",
                        },
                    }
                ],
            },
            {"role": "assistant", "content": "final reply"},
        ],
    )
    def test_run_handles_tool_call_then_returns_final_reply(self, mock_call_llm):
        agent = Agent()
        output = agent.run(AgentInput(session_id="session-a", user_input="帮我测试工具"))

        self.assertEqual(output.reply, "final reply")
        self.assertEqual(mock_call_llm.call_count, 2)

    @patch(
        "agent_prototype.runtime.agent_runtime.call_llm",
        side_effect=[
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_001",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": "{\"path\": \"/tmp\", \"content\": \"hello\"}",
                        },
                    }
                ],
            },
            {"role": "assistant", "content": "final reply after error"},
        ],
    )
    def test_run_records_tool_error_trace(self, mock_call_llm):
        agent = Agent()
        output = agent.run(AgentInput(session_id="session-a", user_input="帮我测试错误 trace"))

        self.assertEqual(output.reply, "final reply after error")
        self.assertEqual(mock_call_llm.call_count, 2)

    @patch(
        "agent_prototype.runtime.agent_runtime.call_llm",
        side_effect=[
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_001",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": "{\"path\": \"demo.txt\", \"content\": \"hello\"}",
                        },
                    }
                ],
            }
        ],
    )
    def test_run_rejects_disallowed_tool_call(self, mock_call_llm):
        agent = Agent(
            definition=AgentDefinition(
                id="default",
                name="Default Agent",
                system_prompt="你是一个助手",
                description=None,
                tool_names=["echo_tool"],
            )
        )

        with self.assertRaises(ValueError) as ctx:
            agent.run(AgentInput(session_id="session-a", user_input="帮我测试权限"))

        self.assertIn("Tool not allowed:write_file", str(ctx.exception))
        self.assertEqual(mock_call_llm.call_count, 1)
