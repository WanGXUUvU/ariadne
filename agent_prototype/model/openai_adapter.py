import os
import json
import time,httpx
from typing import Any, Optional,Iterator,AsyncIterator

import requests

from ..core.schemas import ChatMessage
from .adapter import ModelAdapter
from .model_types import ModelRequest, ModelResponse, ModelUsage,ModelStreamEvent

BASE_URL = "https://token.sensenova.cn/v1"
DEFAULT_MODEL = "sensenova-6.7-flash-lite"


class ChatCompletionsAdapter(ModelAdapter):
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = BASE_URL,
        model: str = DEFAULT_MODEL,
    ):
        self.api_key = api_key or os.environ.get("API_KEY")
        self.base_url = base_url
        self.model = model

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
            "thinking": {"type": "disabled"},
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
            "thinking": {"type": "disabled"},
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
                continue
            choice = choices[0]
            delta = choice.get("delta", {})
            finish_reason=choice.get("finish_reason")
            content = delta.get("content")
            tool_calls=delta.get("tool_calls")
            yield ModelStreamEvent(
                type="delta" if content else ("tool_call_delta" if tool_calls else "done"),
                content_delta=content,
                finish_reason=finish_reason,
                raw_event=delta,   # tool_calls 碎片放这里，上层去拼
            )
                        
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
            "thinking": {"type": "disabled"},
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
                        continue
                    choice = choices[0]
                    delta = choice.get("delta", {})
                    finish_reason=choice.get("finish_reason")
                    content = delta.get("content")
                    tool_calls=delta.get("tool_calls")
                    yield ModelStreamEvent(
                        type="delta" if content else ("tool_call_delta" if tool_calls else "done"),
                        content_delta=content,
                        finish_reason=finish_reason,
                        raw_event=delta,   # tool_calls 碎片放这里，上层去拼
                    )
