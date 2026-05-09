import unittest
from unittest.mock import Mock, patch

import requests

from agent_prototype.model.openai_adapter import call_llm


class TestLlmClient(unittest.TestCase):
    @patch.dict("os.environ", {"SENSENOVA_API_KEY": "test-key"}, clear=False)
    @patch("agent_prototype.model.openai_adapter.requests.post")
    def test_call_llm_wraps_http_error_with_runtime_error(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "upstream failed"
        mock_response.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
        mock_post.return_value = mock_response

        with self.assertRaises(RuntimeError) as ctx:
            call_llm([{"role": "user", "content": "你好"}])

        self.assertIn("LLM request failed", str(ctx.exception))
        self.assertIn("status=500", str(ctx.exception))
        self.assertIn("body=upstream failed", str(ctx.exception))
        mock_response.raise_for_status.assert_called_once()
        mock_response.json.assert_not_called()

    @patch.dict("os.environ", {"SENSENOVA_API_KEY": "test-key"}, clear=False)
    @patch("agent_prototype.model.openai_adapter.requests.post")
    def test_call_llm_raises_when_choices_missing(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {}
        mock_post.return_value = mock_response

        with self.assertRaises(ValueError) as ctx:
            call_llm([{"role": "user", "content": "你好"}])

        self.assertEqual(str(ctx.exception), "LLM response missing choices")

    @patch.dict("os.environ", {"SENSENOVA_API_KEY": "test-key"}, clear=False)
    @patch("agent_prototype.model.openai_adapter.requests.post")
    def test_call_llm_raises_when_message_missing(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"choices": [{}]}
        mock_post.return_value = mock_response

        with self.assertRaises(ValueError) as ctx:
            call_llm([{"role": "user", "content": "你好"}])

        self.assertEqual(str(ctx.exception), "LLM response missing message")
