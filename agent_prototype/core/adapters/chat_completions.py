"""
[L1 核心层 - Chat Completions 适配器]

封装大模型的 API 通信接口（如 SenseNova、OpenAI），将通用模型请求（ModelRequest）转换为服务商特定的 HTTP 请求。
对模型返回的流式 SSE 数据帧进行高内聚的有状态解析。
转换并输出统一的模型响应结构（ModelResponse / StreamChunk）。

上游依赖：L8 执行层 (AgentRunner)、L6 历史压缩层 (HistoryCompactor)。
下游依赖：物理大模型外部 API 服务。
"""

import os
import json
import time, httpx, asyncio
from typing import Any, Optional, Iterator, AsyncIterator

import requests

from agent_prototype.core.types import ChatMessage
from agent_prototype.core.types import ModelAdapter
from agent_prototype.core.types import ModelRequest, ModelResponse, ModelUsage, StreamChunk


class ChatCompletionsAdapter(ModelAdapter):
    """大模型 Chat Completions 通信适配器 (OOP)

    这个类是"大模型皇家同声传译翻译官（API 适配器）"。
    它的核心职责是当系统想找 AI 聊天时，负责把标准的对话请求翻译成不同供应商（比如 OpenAI、DeepSeek）听得懂的 HTTP 格式发过去。
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        extra_payload: Optional[dict] = None,
        thinking_style: str = "none",
    ):
        self.api_key = api_key or os.environ.get("API_KEY")
        self.base_url = base_url
        self.model = model
        self.extra_payload = extra_payload or {}
        self.thinking_style = thinking_style
        self._in_think = False
        self._tag_buf = ""

    # ── thinking 解析工具 ──────────────────────────────────────────────────

    def _reset_think_state(self) -> None:
        self._in_think = False
        self._tag_buf = ""

    @staticmethod
    def _partial_suffix(text: str, tag: str) -> str:
        for i in range(min(len(tag) - 1, len(text)), 0, -1):
            if text.endswith(tag[:i]):
                return text[-i:]
        return ""

    def _parse_think_content(self, raw: str, finish_reason) -> list[StreamChunk]:
        events: list[StreamChunk] = []
        text = self._tag_buf + raw
        self._tag_buf = ""

        while text:
            if self._in_think:
                close_idx = text.find("</think_tag>")
                if close_idx == -1:
                    partial = self._partial_suffix(text, "</think_tag>")
                    emit = text[: len(text) - len(partial)] if partial else text
                    if emit:
                        events.append(StreamChunk(type="thinking_delta", thinking_delta=emit))
                    self._tag_buf = partial
                    break
                if close_idx > 0:
                    events.append(
                        StreamChunk(type="thinking_delta", thinking_delta=text[:close_idx])
                    )
                self._in_think = False
                text = text[close_idx + len("</think_tag>") :]
            else:
                open_idx = text.find("<think_tag>")
                if open_idx == -1:
                    partial = self._partial_suffix(text, "<think_tag>")
                    emit = text[: len(text) - len(partial)] if partial else text
                    if emit:
                        events.append(
                            StreamChunk(
                                type="delta",
                                content_delta=emit,
                                finish_reason=finish_reason,
                            )
                        )
                    self._tag_buf = partial
                    break
                if open_idx > 0:
                    events.append(StreamChunk(type="delta", content_delta=text[:open_idx]))
                self._in_think = True
                text = text[open_idx + len("<think_tag>") :]

        return events

    def _parse_delta(self, delta: dict, finish_reason) -> list[StreamChunk]:
        tool_calls = delta.get("tool_calls")
        content = delta.get("content")

        if self.thinking_style == "always_on_style":
            if content:
                return self._parse_think_content(content, finish_reason)
            return [
                StreamChunk(
                    type="tool_call_delta" if tool_calls else "done",
                    finish_reason=finish_reason,
                    raw_event=delta,
                )
            ]

        thinking = (
            delta.get("reasoning_content")
            or delta.get("thinking_content")
            or delta.get("reasoning")
        )
        if thinking:
            return [
                StreamChunk(type="thinking_delta", thinking_delta=thinking, raw_event=delta)
            ]

        return [
            StreamChunk(
                type="delta" if content else ("tool_call_delta" if tool_calls else "done"),
                content_delta=content,
                finish_reason=finish_reason,
                raw_event=delta,
            )
        ]

    # ── 请求方法 ──────────────────────────────────────────────────────────

    def generate(self, request: ModelRequest) -> ModelResponse:
        if not self.api_key:
            raise RuntimeError("Missing API_KEY")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": request.config.model or self.model,
            "messages": [msg.model_dump(exclude_none=True) for msg in request.messages],
            "stream": request.config.stream,
        }

        if request.config.temperature is not None:
            payload["temperature"] = request.config.temperature
        if request.config.top_p is not None:
            payload["top_p"] = request.config.top_p
        if request.config.max_output_tokens is not None:
            payload["max_tokens"] = request.config.max_output_tokens
        if request.config.tool_choice is not None:
            payload["tool_choice"] = request.config.tool_choice
        elif request.tools:
            payload["tool_choice"] = "auto"

        if request.tools:
            payload["tools"] = request.tools

        payload.update(request.config.provider_options)
        payload.update(self.extra_payload)

        max_retries = 3
        initial_delay = 1.0
        backoff_factor = 2.0

        response = None
        for attempt in range(max_retries + 1):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=2100)
                response.raise_for_status()
                break
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                if attempt == max_retries:
                    raise RuntimeError(
                        f"LLM request failed due to network/timeout error after {max_retries} retries: {exc}"
                    ) from exc
            except requests.exceptions.HTTPError as exc:
                status_code = response.status_code if response is not None else 500
                text = response.text if response is not None else ""

                is_retryable = (
                    status_code == 429
                    or (500 <= status_code < 600)
                    or (status_code == 400 and "engine is not available temporarily" in text)
                )
                if not is_retryable or attempt == max_retries:
                    raise RuntimeError(
                        f"LLM request failed: url={url}, model={payload['model']}, "
                        f"status={status_code}, body={text}"
                    ) from exc

            delay = initial_delay * (backoff_factor**attempt)
            time.sleep(delay)

        data = response.json()
        choices = data.get("choices")
        if not choices:
            raise ValueError("LLM response missing choices")

        message_data = choices[0].get("message")
        if message_data is None:
            raise ValueError("LLM response missing message")

        assistant_message = ChatMessage.model_validate(message_data)

        usage_data = data.get("usage") or {}
        usage = ModelUsage(
            input_tokens=usage_data.get("prompt_tokens"),
            output_tokens=usage_data.get("completion_tokens"),
            total_tokens=usage_data.get("total_tokens"),
            details=usage_data,
        )

        return ModelResponse(
            assistant_message=assistant_message,
            id=data.get("id"),
            model=data.get("model") or payload["model"],
            status="completed",
            finish_reason=choices[0].get("finish_reason"),
            usage=usage,
            raw_response=data,
            provider_meta={},
        )

    def stream_generate(self, request: ModelRequest) -> Iterator[StreamChunk]:
        if not self.api_key:
            raise RuntimeError("Missing API_KEY")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": request.config.model or self.model,
            "messages": [msg.model_dump(exclude_none=True) for msg in request.messages],
            "stream": True,
        }
        if request.config.temperature is not None:
            payload["temperature"] = request.config.temperature
        if request.config.top_p is not None:
            payload["top_p"] = request.config.top_p
        if request.config.max_output_tokens is not None:
            payload["max_tokens"] = request.config.max_output_tokens
        if request.config.tool_choice is not None:
            payload["tool_choice"] = request.config.tool_choice
        elif request.tools:
            payload["tool_choice"] = "auto"

        if request.tools:
            payload["tools"] = request.tools

        payload.update(request.config.provider_options)
        payload.update(self.extra_payload)
        payload["stream_options"] = {"include_usage": True}
        max_retries = 3
        initial_delay = 1.0
        backoff_factor = 2.0

        response = None
        for attempt in range(max_retries + 1):
            try:
                response = requests.post(
                    url, headers=headers, json=payload, timeout=2100, stream=True
                )
                response.raise_for_status()
                break
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                if attempt == max_retries:
                    raise RuntimeError(
                        f"LLM request failed due to network/timeout error after {max_retries} retries: {exc}"
                    ) from exc
            except requests.exceptions.HTTPError as exc:
                status_code = response.status_code if response is not None else 500
                text = response.text if response is not None else ""
                try:
                    err_body = response.json() if response is not None else {}
                except Exception:
                    err_body = text

                is_retryable = (
                    status_code == 429
                    or (500 <= status_code < 600)
                    or (status_code == 400 and "engine is not available temporarily" in text)
                )
                if not is_retryable or attempt == max_retries:
                    raise RuntimeError(
                        f"LLM request failed: url={url}, model={payload['model']}, "
                        f"status={status_code}, body={err_body}"
                    ) from exc

            delay = initial_delay * (backoff_factor**attempt)
            time.sleep(delay)

        self._reset_think_state()
        for line in response.iter_lines():
            if not line:
                continue
            text = line.decode("utf-8") if isinstance(line, bytes) else line
            if not text.startswith("data:"):
                continue
            text = text[len("data:") :].strip()
            if text == "[DONE]":
                break
            chunk = json.loads(text)
            choices = chunk.get("choices") or []
            if not choices:
                usage_data = chunk.get("usage")
                if usage_data:
                    yield StreamChunk(
                        type="done",
                        usage=ModelUsage(
                            input_tokens=usage_data.get("prompt_tokens"),
                            output_tokens=usage_data.get("completion_tokens"),
                            total_tokens=usage_data.get("total_tokens"),
                            details=usage_data,
                        ),
                    )
                continue
            choice = choices[0]
            delta = choice.get("delta", {})
            finish_reason = choice.get("finish_reason")
            for event in self._parse_delta(delta, finish_reason):
                yield event

    async def async_stream_generate(self, request: ModelRequest) -> AsyncIterator[StreamChunk]:
        if not self.api_key:
            raise RuntimeError("Missing API_KEY")

        url = f"{self.base_url}/chat/completions"
        headers = {
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": request.config.model or self.model,
            "messages": [msg.model_dump(exclude_none=True) for msg in request.messages],
            "stream": True,
        }
        if request.config.temperature is not None:
            payload["temperature"] = request.config.temperature
        if request.config.top_p is not None:
            payload["top_p"] = request.config.top_p
        if request.config.max_output_tokens is not None:
            payload["max_tokens"] = request.config.max_output_tokens
        if request.config.tool_choice is not None:
            payload["tool_choice"] = request.config.tool_choice
        elif request.tools:
            payload["tool_choice"] = "auto"

        if request.tools:
            payload["tools"] = request.tools

        payload.update(request.config.provider_options)
        payload.update(self.extra_payload)
        payload["stream_options"] = {"include_usage": True}

        max_retries = 3  # 最大重试次数
        initial_delay = 1.0  # 初始等待 1.0s
        backoff_factor = 2.0  # 乘数因子

        ctx = None  # 用来保存 httpx 的 Stream 上下文管理器
        response = None  # 用来保存成功的响应对象
        self._reset_think_state()
        # 异步地帮我创建一个网络客户端，并且无论如何，等我退出这段代码时，异步地帮我把连接池全部关闭
        async with httpx.AsyncClient(timeout=2100) as client:
            # 先和对方握个手，建立连接。数据你别急着下载，我后面自己一点点读
            for attempt in range(max_retries + 1):
                try:
                    ctx = client.stream("POST", url, headers=headers, json=payload)
                    response = await ctx.__aenter__()
                    response.raise_for_status()
                    break
                except Exception as exc:
                    if ctx is not None:
                        await ctx.__aexit__(None, None, None)
                        ctx = None
                    if attempt == max_retries:
                        raise RuntimeError(
                            f"LLM stream request failed after {max_retries} retries: {exc}"
                        ) from exc
                    delay = initial_delay * (backoff_factor**attempt)
                    await asyncio.sleep(delay)

            try:
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if not line.startswith("data:"):
                        continue
                    text = line[len("data:") :].strip()
                    if text == "[DONE]":
                        break
                    chunk = json.loads(text)
                    choices = chunk.get("choices") or []
                    if not choices:
                        usage_data = chunk.get("usage")
                        if usage_data:
                            yield StreamChunk(
                                type="done",
                                usage=ModelUsage(
                                    input_tokens=usage_data.get("prompt_tokens"),
                                    output_tokens=usage_data.get("completion_tokens"),
                                    total_tokens=usage_data.get("total_tokens"),
                                    details=usage_data,
                                ),
                            )
                        continue
                    choice = choices[0]
                    delta = choice.get("delta", {})
                    finish_reason = choice.get("finish_reason")
                    for event in self._parse_delta(delta, finish_reason):
                        yield event

            finally:
                if ctx is not None:
                    await ctx.__aexit__(None, None, None)
