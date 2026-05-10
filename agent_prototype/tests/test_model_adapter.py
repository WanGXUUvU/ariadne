import unittest
from unittest.mock import Mock, patch

import requests

from agent_prototype.core.schemas import ChatMessage
from agent_prototype.model.model_types import ModelConfig, ModelRequest
from agent_prototype.model.openai_adapter import ChatCompletionsAdapter


class TestChatCompletionsAdapter(unittest.TestCase):
    @patch.dict("os.environ", {"API_KEY": "test-key"}, clear=False)
    @patch("agent_prototype.model.openai_adapter.requests.post")
    def test_generate_wraps_http_error_with_runtime_error(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "upstream failed"
        mock_response.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
        mock_post.return_value = mock_response

        adapter = ChatCompletionsAdapter()
        request = ModelRequest(
            messages=[ChatMessage(role="user", content="你好")],
            tools=[],
            config=ModelConfig(stream=False),
        )

        with self.assertRaises(RuntimeError) as ctx:
            adapter.generate(request)

        self.assertIn("LLM request failed", str(ctx.exception))
        self.assertIn("status=500", str(ctx.exception))
        self.assertIn("body=upstream failed", str(ctx.exception))
        mock_response.raise_for_status.assert_called_once()
        mock_response.json.assert_not_called()

    @patch.dict("os.environ", {"API_KEY": "test-key"}, clear=False)
    @patch("agent_prototype.model.openai_adapter.requests.post")
    def test_generate_raises_when_choices_missing(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {}
        mock_post.return_value = mock_response

        adapter = ChatCompletionsAdapter()
        request = ModelRequest(
            messages=[ChatMessage(role="user", content="你好")],
            tools=[],
            config=ModelConfig(stream=False),
        )

        with self.assertRaises(ValueError) as ctx:
            adapter.generate(request)

        self.assertEqual(str(ctx.exception), "LLM response missing choices")

    @patch.dict("os.environ", {"API_KEY": "test-key"}, clear=False)
    @patch("agent_prototype.model.openai_adapter.requests.post")
    def test_generate_raises_when_message_missing(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"choices": [{}]}
        mock_post.return_value = mock_response

        adapter = ChatCompletionsAdapter()
        request = ModelRequest(
            messages=[ChatMessage(role="user", content="你好")],
            tools=[],
            config=ModelConfig(stream=False),
        )

        with self.assertRaises(ValueError) as ctx:
            adapter.generate(request)

        self.assertEqual(str(ctx.exception), "LLM response missing message")

    @patch.dict("os.environ", {"API_KEY": "test-key"}, clear=False)
    @patch("agent_prototype.model.openai_adapter.requests.post")
    def test_generate_returns_model_response(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "id": "resp_123",
            "model": "deepseek-v4-flash",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": "你好，我是助手",
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 8,
                "total_tokens": 20,
            },
        }
        mock_post.return_value = mock_response

        adapter = ChatCompletionsAdapter()
        request = ModelRequest(
            messages=[ChatMessage(role="user", content="你好")],
            tools=[],
            config=ModelConfig(stream=False),
        )

        response = adapter.generate(request)

        self.assertEqual(response.id, "resp_123")
        self.assertEqual(response.model, "deepseek-v4-flash")
        self.assertEqual(response.finish_reason, "stop")
        self.assertEqual(response.content, "你好，我是助手")
        self.assertEqual(response.usage.input_tokens, 12)
        self.assertEqual(response.usage.output_tokens, 8)
        self.assertEqual(response.usage.total_tokens, 20)
        self.assertEqual(mock_post.call_args.kwargs["json"]["messages"][0]["role"], "user")
        self.assertEqual(mock_post.call_args.kwargs["json"]["messages"][0]["content"], "你好")
