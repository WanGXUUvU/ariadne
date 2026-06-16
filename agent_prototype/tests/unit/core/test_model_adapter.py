import unittest
from unittest.mock import Mock, patch

import requests

from agent_prototype.core.types import ChatMessage, ModelConfig, ModelRequest
from agent_prototype.core.adapters.chat_completions import ChatCompletionsAdapter


class TestChatCompletionsAdapter(unittest.TestCase):
    @patch.dict("os.environ", {"API_KEY": "test-key"}, clear=False)
    @patch("agent_prototype.core.adapters.chat_completions.requests.post")
    def test_generate_wraps_http_error_with_runtime_error(self, mock_post):
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.text = "upstream failed"
        mock_response.raise_for_status.side_effect = requests.HTTPError(
            "403 Forbidden", response=mock_response
        )
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
        self.assertIn("status=403", str(ctx.exception))
        self.assertIn("body=upstream failed", str(ctx.exception))
        mock_response.raise_for_status.assert_called_once()
        mock_response.json.assert_not_called()

    @patch.dict("os.environ", {"API_KEY": "test-key"}, clear=False)
    @patch("agent_prototype.core.adapters.chat_completions.requests.post")
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
    @patch("agent_prototype.core.adapters.chat_completions.requests.post")
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
    @patch("agent_prototype.core.adapters.chat_completions.requests.post")
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
        self.assertEqual(
            mock_post.call_args.kwargs["json"]["messages"][0]["role"], "user"
        )
        self.assertEqual(
            mock_post.call_args.kwargs["json"]["messages"][0]["content"], "你好"
        )

    def test_parse_delta_splits_combined_fields_in_stable_order(self):
        adapter = ChatCompletionsAdapter()

        events = adapter._parse_delta(
            {
                "reasoning_content": "先想",
                "content": "我先查一下",
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "call_001",
                        "function": {
                            "name": "echo_tool",
                            "arguments": '{"text":',
                        },
                    }
                ],
            },
            finish_reason="tool_calls",
        )

        self.assertEqual(
            [event.type for event in events],
            [
                "thinking_delta",
                "content_delta",
                "tool_call_delta",
            ],
        )
        self.assertEqual(events[0].thinking_delta, "先想")
        self.assertEqual(events[1].content_delta, "我先查一下")
        self.assertEqual(events[2].tool_call_delta["tool_calls"][0]["id"], "call_001")

    def test_parse_delta_preserves_tool_call_after_always_on_content(self):
        adapter = ChatCompletionsAdapter(thinking_style="always_on_style")

        events = adapter._parse_delta(
            {
                "content": "我先查一下",
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "call_001",
                        "function": {
                            "name": "echo_tool",
                            "arguments": '{"text":',
                        },
                    }
                ],
            },
            finish_reason="tool_calls",
        )

        self.assertEqual(
            [event.type for event in events],
            [
                "content_delta",
                "tool_call_delta",
            ],
        )
        self.assertEqual(events[0].content_delta, "我先查一下")
        self.assertEqual(events[1].tool_call_delta["tool_calls"][0]["id"], "call_001")

    @patch.dict("os.environ", {"API_KEY": "test-key"}, clear=False)
    @patch("agent_prototype.core.adapters.chat_completions.requests.post")
    @patch("agent_prototype.core.adapters.chat_completions.time.sleep")
    def test_generate_retry_success(self, mock_sleep, mock_post):
        # 1st attempt: 429
        mock_resp_429 = Mock()
        mock_resp_429.status_code = 429
        mock_resp_429.text = "Too Many Requests"
        mock_resp_429.raise_for_status.side_effect = requests.HTTPError(
            "429 Too Many Requests", response=mock_resp_429
        )

        # 2nd attempt: 503
        mock_resp_503 = Mock()
        mock_resp_503.status_code = 503
        mock_resp_503.text = "Service Unavailable"
        mock_resp_503.raise_for_status.side_effect = requests.HTTPError(
            "503 Service Unavailable", response=mock_resp_503
        )

        # 3rd attempt: 200 (Success)
        mock_resp_200 = Mock()
        mock_resp_200.status_code = 200
        mock_resp_200.raise_for_status.return_value = None
        mock_resp_200.json.return_value = {
            "id": "resp_ok",
            "model": "test-model",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "role": "assistant",
                        "content": "Success after retries",
                    },
                }
            ],
            "usage": {},
        }

        mock_post.side_effect = [mock_resp_429, mock_resp_503, mock_resp_200]

        adapter = ChatCompletionsAdapter()
        request = ModelRequest(
            messages=[ChatMessage(role="user", content="Test")],
            tools=[],
            config=ModelConfig(stream=False),
        )

        response = adapter.generate(request)
        self.assertEqual(response.content, "Success after retries")
        self.assertEqual(mock_post.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)
        mock_sleep.assert_any_call(1.0)
        mock_sleep.assert_any_call(2.0)

    @patch.dict("os.environ", {"API_KEY": "test-key"}, clear=False)
    @patch("agent_prototype.core.adapters.chat_completions.requests.post")
    @patch("agent_prototype.core.adapters.chat_completions.time.sleep")
    def test_generate_retry_exhausted(self, mock_sleep, mock_post):
        # Mock requests.post always raising a Timeout exception
        mock_post.side_effect = requests.exceptions.Timeout("Connection timed out")

        adapter = ChatCompletionsAdapter()
        request = ModelRequest(
            messages=[ChatMessage(role="user", content="Test")],
            tools=[],
            config=ModelConfig(stream=False),
        )

        with self.assertRaises(RuntimeError) as ctx:
            adapter.generate(request)

        self.assertIn(
            "failed due to network/timeout error after 3 retries", str(ctx.exception)
        )
        self.assertEqual(mock_post.call_count, 4)  # original + 3 retries
        self.assertEqual(mock_sleep.call_count, 3)
        mock_sleep.assert_any_call(1.0)
        mock_sleep.assert_any_call(2.0)
        mock_sleep.assert_any_call(4.0)

    @patch.dict("os.environ", {"API_KEY": "test-key"}, clear=False)
    @patch("agent_prototype.core.adapters.chat_completions.httpx.AsyncClient")
    @patch("agent_prototype.core.adapters.chat_completions.asyncio.sleep")
    def test_async_stream_generate_retry_success(self, mock_sleep, mock_client_cls):
        import httpx
        from unittest.mock import AsyncMock

        mock_client = mock_client_cls.return_value.__aenter__.return_value
        # Make stream a synchronous mock to return ctx immediately instead of returning a coroutine
        mock_client.stream = Mock()

        # 1st attempt: 429
        mock_resp_429 = Mock()
        mock_resp_429.status_code = 429

        async def mock_aread_429():
            return b"Too Many Requests"

        mock_resp_429.aread = mock_aread_429

        mock_ctx_429 = Mock()
        mock_ctx_429.__aenter__ = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "429 Too Many Requests", request=Mock(), response=mock_resp_429
            )
        )
        mock_ctx_429.__aexit__ = AsyncMock()

        # 2nd attempt: 200 (Success)
        mock_resp_200 = Mock()
        mock_resp_200.status_code = 200
        mock_resp_200.raise_for_status.return_value = None

        async def mock_aiter_lines():
            yield 'data: {"choices": [{"delta": {"content": "Hello"}}]}'
            yield "data: [DONE]"

        mock_resp_200.aiter_lines = mock_aiter_lines

        mock_ctx_200 = Mock()
        mock_ctx_200.__aenter__ = AsyncMock(return_value=mock_resp_200)
        mock_ctx_200.__aexit__ = AsyncMock()

        mock_client.stream.side_effect = [mock_ctx_429, mock_ctx_200]

        adapter = ChatCompletionsAdapter()
        request = ModelRequest(
            messages=[ChatMessage(role="user", content="Test")],
            tools=[],
            config=ModelConfig(stream=True),
        )

        events = []

        async def collect():
            async for ev in adapter.async_stream_generate(request):
                events.append(ev)

        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(collect())

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].content_delta, "Hello")
        self.assertEqual(mock_client.stream.call_count, 2)
        mock_sleep.assert_called_once_with(1.0)

    @patch.dict("os.environ", {"API_KEY": "test-key"}, clear=False)
    @patch("agent_prototype.core.adapters.chat_completions.httpx.AsyncClient")
    @patch("agent_prototype.core.adapters.chat_completions.asyncio.sleep")
    def test_async_stream_generate_retry_exhausted(self, mock_sleep, mock_client_cls):
        import httpx
        from unittest.mock import AsyncMock

        mock_client = mock_client_cls.return_value.__aenter__.return_value
        # Make stream a synchronous mock to return ctx immediately instead of returning a coroutine
        mock_client.stream = Mock()

        # All attempts raise TimeoutException during connection enter
        mock_ctx = Mock()
        mock_ctx.__aenter__ = AsyncMock(
            side_effect=httpx.TimeoutException("Connection timed out", request=Mock())
        )
        mock_ctx.__aexit__ = AsyncMock()

        mock_client.stream.return_value = mock_ctx

        adapter = ChatCompletionsAdapter()
        request = ModelRequest(
            messages=[ChatMessage(role="user", content="Test")],
            tools=[],
            config=ModelConfig(stream=True),
        )

        events = []

        async def collect():
            async for ev in adapter.async_stream_generate(request):
                events.append(ev)

        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        with self.assertRaises(RuntimeError) as ctx:
            loop.run_until_complete(collect())

        self.assertIn("failed after 3 retries", str(ctx.exception))
        self.assertEqual(mock_client.stream.call_count, 4)
        self.assertEqual(mock_sleep.call_count, 3)
        mock_sleep.assert_any_call(1.0)
        mock_sleep.assert_any_call(2.0)
        mock_sleep.assert_any_call(4.0)
