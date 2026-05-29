"""
[L1 核心层 - Chat Completions 适配器]

封装大模型的 API 通信接口（如 SenseNova、OpenAI），将通用模型请求（ModelRequest）转换为服务商特定的 HTTP 请求。
对模型返回的流式 SSE 数据帧进行高内聚的有状态解析。
转换并输出统一的模型响应结构（ModelResponse / ModelStreamEvent）。

上游依赖：L8 执行层 (AgentRunner)、L6 历史压缩层 (HistoryCompactor)。
下游依赖：物理大模型外部 API 服务。
"""

import os
import json
import time, httpx
from typing import Any, Optional, Iterator, AsyncIterator

import requests

from agent_prototype.core.types import ChatMessage
from agent_prototype.core.types import ModelAdapter
from agent_prototype.core.types import ModelRequest, ModelResponse, ModelUsage, ModelStreamEvent


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

    def _parse_think_content(self, raw: str, finish_reason) -> list[ModelStreamEvent]:
        events: list[ModelStreamEvent] = []
        text = self._tag_buf + raw
        self._tag_buf = ""

        while text:
            if self._in_think:
                close_idx = text.find("</think_tag>")
                if close_idx == -1:
                    partial = self._partial_suffix(text, "</think_tag>")
                    emit = text[: len(text) - len(partial)] if partial else text
                    if emit:
                        events.append(ModelStreamEvent(type="thinking_delta", thinking_delta=emit))
                    self._tag_buf = partial
                    break
                if close_idx > 0:
                    events.append(
                        ModelStreamEvent(type="thinking_delta", thinking_delta=text[:close_idx])
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
                            ModelStreamEvent(
                                type="delta",
                                content_delta=emit,
                                finish_reason=finish_reason,
                            )
                        )
                    self._tag_buf = partial
                    break
                if open_idx > 0:
                    events.append(ModelStreamEvent(type="delta", content_delta=text[:open_idx]))
                self._in_think = True
                text = text[open_idx + len("<think_tag>") :]

        return events

    def _parse_delta(self, delta: dict, finish_reason) -> list[ModelStreamEvent]:
        tool_calls = delta.get("tool_calls")
        content = delta.get("content")

        if self.thinking_style == "always_on_style":
            if content:
                return self._parse_think_content(content, finish_reason)
            return [
                ModelStreamEvent(
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
                ModelStreamEvent(type="thinking_delta", thinking_delta=thinking, raw_event=delta)
            ]

        return [
            ModelStreamEvent(
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

        response = None
        for attempt in range(2):
            response = requests.post(url, headers=headers, json=payload, timeout=2100)

            try:
                response.raise_for_status()
                break
            except requests.HTTPError as exc:
                retryable_engine_error = (
                    response.status_code == 400
                    and "engine is not available temporarily" in (response.text or "")
                )
                if attempt == 0 and retryable_engine_error:
                    time.sleep(0.5)
                    continue
                raise RuntimeError(
                    f"LLM request failed: url={url}, model={payload['model']}, "
                    f"status={response.status_code}, body={response.text}"
                ) from exc

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

    def stream_generate(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
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
        response = None
        for attempt in range(2):
            response = requests.post(url, headers=headers, json=payload, timeout=2100, stream=True)
            try:
                response.raise_for_status()
                break
            except requests.HTTPError as exc:
                retryable_engine_error = (
                    response.status_code == 400
                    and "engine is not available temporarily" in (response.text or "")
                )
                if attempt == 0 and retryable_engine_error:
                    time.sleep(0.5)
                    continue
                err_body = ""
                try:
                    err_body = response.json()
                except Exception:
                    err_body = response.text

                raise RuntimeError(
                    f"LLM request failed: url={url}, model={payload['model']}, "
                    f"status={response.status_code}, body={err_body}"
                ) from exc

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
                    yield ModelStreamEvent(
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

    async def async_stream_generate(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
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
        self._reset_think_state()
        async with httpx.AsyncClient(timeout=2100) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
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
                            yield ModelStreamEvent(
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
