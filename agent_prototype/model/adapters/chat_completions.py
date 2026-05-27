"""
[九层模型 - L1 模型层 (Model Layer)]

文件职责：
- 封装大模型的 API 通信接口（如 SenseNova、OpenAI），将通用模型请求（ModelRequest）转换为服务商特定的 HTTP 请求。
- 对模型返回的流式 SSE 数据帧进行高内聚的有状态解析（例如：思维链标签 <think>...</think> 的智能提取）。
- 转换并输出统一的模型响应结构（ModelResponse / ModelStreamEvent）。

上游依赖：L8 执行层 (AgentRunner)、L6 历史压缩层 (HistoryCompactor)。
下游依赖：物理大模型外部 API 服务。
"""
import os
import json
import time,httpx
from typing import Any, Optional,Iterator,AsyncIterator

import requests

from agent_prototype.model.types.domain import ChatMessage
from .protocol import ModelAdapter
from agent_prototype.model.types.model_types import ModelRequest, ModelResponse, ModelUsage, ModelStreamEvent



class ChatCompletionsAdapter(ModelAdapter):
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url:  Optional[str]=None,
        model:  Optional[str]=None,
        extra_payload: Optional[dict] = None,
        thinking_style: str = "none",
    ):
        self.api_key = api_key or os.environ.get("API_KEY")
        self.base_url = base_url
        self.model = model
        self.extra_payload = extra_payload or {}
        self.thinking_style = thinking_style
        self._in_think = False   # <think>...</think> 标签解析状态
        self._tag_buf = ""       # 跨 chunk 的不完整标签缓冲

    # ── thinking 解析工具 ──────────────────────────────────────────────────

    def _reset_think_state(self) -> None:
        """每次流式请求开始前重置跨 chunk 解析状态。"""
        self._in_think = False
        self._tag_buf = ""

    @staticmethod
    def _partial_suffix(text: str, tag: str) -> str:
        """返回 text 末尾与 tag 开头匹配的最长前缀。
        用于检测 chunk 边界处被切断的不完整标签，如 "<thi" 可能是 "<think>" 的开头。
        """
        for i in range(min(len(tag) - 1, len(text)), 0, -1):
            if text.endswith(tag[:i]):
                return text[-i:]
        return ""

    def _parse_think_content(self, raw: str, finish_reason) -> list[ModelStreamEvent]:
        """将含 <think>...</think> 标签的 content 流切分为事件列表。

        有状态：_in_think 和 _tag_buf 在多次调用间保持，直到 _reset_think_state() 重置。
        同一个 delta 可能产生多个事件（如 </think>正文 → thinking_delta + delta）。
        """
        events: list[ModelStreamEvent] = []
        text = self._tag_buf + raw
        self._tag_buf = ""

        while text:
            if self._in_think:
                close_idx = text.find("</think>")
                if close_idx == -1:
                    # 检查末尾是否是 </think> 的部分前缀，缓冲起来等下一个 chunk
                    partial = self._partial_suffix(text, "</think>")
                    emit = text[: len(text) - len(partial)] if partial else text
                    if emit:
                        events.append(ModelStreamEvent(type="thinking_delta", thinking_delta=emit))
                    self._tag_buf = partial
                    break
                if close_idx > 0:
                    events.append(ModelStreamEvent(type="thinking_delta", thinking_delta=text[:close_idx]))
                self._in_think = False
                text = text[close_idx + len("</think>"):]
            else:
                open_idx = text.find("<think>")
                if open_idx == -1:
                    partial = self._partial_suffix(text, "<think>")
                    emit = text[: len(text) - len(partial)] if partial else text
                    if emit:
                        events.append(ModelStreamEvent(
                            type="delta", content_delta=emit, finish_reason=finish_reason,
                        ))
                    self._tag_buf = partial
                    break
                if open_idx > 0:
                    events.append(ModelStreamEvent(type="delta", content_delta=text[:open_idx]))
                self._in_think = True
                text = text[open_idx + len("<think>"):]

        return events

    def _parse_delta(self, delta: dict, finish_reason) -> list[ModelStreamEvent]:
        """将单条 SSE delta 解析为 ModelStreamEvent 列表。

        - always_on_style：thinking 嵌入 content 字段的 <think>...</think> 标签，需有状态解析
        - 其他 style：thinking 在独立字段（reasoning_content / thinking_content / reasoning）
        """
        tool_calls = delta.get("tool_calls")
        content = delta.get("content")

        if self.thinking_style == "always_on_style":
            if content:
                return self._parse_think_content(content, finish_reason)
            return [ModelStreamEvent(
                type="tool_call_delta" if tool_calls else "done",
                finish_reason=finish_reason,
                raw_event=delta,
            )]

        # 标准字段 thinking
        thinking = (delta.get("reasoning_content")
                    or delta.get("thinking_content")
                    or delta.get("reasoning"))
        if thinking:
            return [ModelStreamEvent(type="thinking_delta", thinking_delta=thinking, raw_event=delta)]

        return [ModelStreamEvent(
            type="delta" if content else ("tool_call_delta" if tool_calls else "done"),
            content_delta=content,
            finish_reason=finish_reason,
            raw_event=delta,
        )]

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

    def stream_generate(self, request:ModelRequest)->Iterator[str]:
        """输入：ModelRequest。输出：逐个 yield delta token 字符串。"""

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
            #requests.post(..., stream=True) — 这个 stream=True 是 requests 库的参数，不是 payload 里的，两处都要加
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
                # 处理限流等错误时安全提取 body
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
            text=line.decode("utf-8") if isinstance(line,bytes) else line
            if not text.startswith("data:"):
                continue
            text = text[len("data:"):].strip()
            if text == "[DONE]":
                break
            chunk = json.loads(text)
            choices = chunk.get("choices") or []
            if not choices:
                usage_data=chunk.get("usage")
                if usage_data:
                    yield ModelStreamEvent(
                        type="done",
                        usage=ModelUsage(
                        input_tokens=usage_data.get("prompt_tokens"),
                        output_tokens=usage_data.get("completion_tokens"),
                        total_tokens=usage_data.get("total_tokens"),
                        details=usage_data,
                        )
                    )
                continue
            choice = choices[0]
            delta = choice.get("delta", {})
            finish_reason = choice.get("finish_reason")
            for event in self._parse_delta(delta, finish_reason):
                yield event

    async def async_stream_generate(self, request:ModelRequest)->AsyncIterator[ModelStreamEvent]:
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
        #创建一个异步 HTTP 客户端（client），在代码块里使用它，离开时自动清理连接资源
        async with httpx.AsyncClient(timeout=2100) as client:
            async with client.stream("POST",url,headers=headers,json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                        # 同样在等 SenseNova 生成下一个 token
                        # 但这个等是 await，线程没有被占用
                        # 事件循环趁这 50ms～200ms 去做其他事
                        # 比如检测：前端还在吗？
                        # 如果前端断了，下次 await 时立刻通知
                    if not line:
                        continue
                    if not line.startswith("data:"):
                        #SSE 协议里除了 data: 开头的行，还可能有 event id keep alive
                        continue
                    text = line[len("data:"):].strip()
                    if text == "[DONE]":
                        break
                    chunk = json.loads(text)
                    choices = chunk.get("choices") or []
                    if not choices:
                        usage_data=chunk.get("usage")
                        if usage_data:
                            yield ModelStreamEvent(
                                type="done",
                                usage=ModelUsage(
                                input_tokens=usage_data.get("prompt_tokens"),
                                output_tokens=usage_data.get("completion_tokens"),
                                total_tokens=usage_data.get("total_tokens"),
                                details=usage_data,
                                )
                            )
                        continue
                    choice = choices[0]
                    delta = choice.get("delta", {})
                    finish_reason = choice.get("finish_reason")
                    for event in self._parse_delta(delta, finish_reason):
                        yield event
