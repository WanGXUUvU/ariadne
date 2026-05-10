import os
import time
from typing import Any, Optional

import requests

from ..core.schemas import ChatMessage
from .adapter import ModelAdapter
from .model_types import ModelRequest, ModelResponse, ModelUsage

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
