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
    """大模型 Chat Completions 通信适配器 (OOP)
    
    这个类是“大模型皇家同声传译翻译官（API 适配器）”。
    它的核心职责是当系统想找 AI 聊天时，负责把标准的对话请求翻译成不同供应商（比如 OpenAI、DeepSeek）听得懂的 HTTP 格式发过去。由于很多高级 AI 会吐出“思维链内容”（也就是在思考的过程，一般夹在 `<think>...</think>` 里），这个适配器还非常机智地实现了一个“有状态流式解析器”，能把 AI 实时吐出的字流，智能切分成“AI 正在思考中（thinking_delta）”和“AI 最终回答内容（delta）”的流式事件送给前端，让界面可以优雅地展示 AI 的思考过程。
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url:  Optional[str]=None,
        model:  Optional[str]=None,
        extra_payload: Optional[dict] = None,
        thinking_style: str = "none",
    ):
        """翻译官初始化，穿戴好装备，记好接口地址、密钥（API Key）以及这次想找哪个大模型（model）聊天。
        """
        self.api_key = api_key or os.environ.get("API_KEY")
        self.base_url = base_url
        self.model = model
        self.extra_payload = extra_payload or {}
        self.thinking_style = thinking_style
        self._in_think = False   # <think>...</think> 标签解析状态
        self._tag_buf = ""       # 跨 chunk 的不完整标签缓冲

    # ── thinking 解析工具 ──────────────────────────────────────────────────

    def _reset_think_state(self) -> None:
        """流式对话开始前重置状态。
        因为流式吐字像挤牙膏，在每次跟 AI 开始聊天前，得把“我目前是不是在看思考内容”的标记设为否，并清空上回留下来的半个标签缓存。
        """
        self._in_think = False
        self._tag_buf = ""

    @staticmethod
    def _partial_suffix(text: str, tag: str) -> str:
        """边缘截断检测小助手。
        有时候流式返回一个字一个字蹦，可能刚好把 `<think>` 标签拦腰斩断成 `<thi` 放在了当前的字块（chunk）末尾。这个函数就是用来检查文本末尾是不是刚好匹配 `<think>` 标签的前几个字母，方便下次拼起来。

        需要拿到的东西：
        - text (str): 当前收到的字块尾部文本。
        - tag (str): 想要匹配的完整标签（如 `"<think>"` 或 `"</think>"`）。

        会给出来的结果：
        - str: 匹配上的不完整截断片段（如 `"<thi"`），没匹配上就返回空。
        """
        for i in range(min(len(tag) - 1, len(text)), 0, -1):
            if text.endswith(tag[:i]):
                return text[-i:]
        return ""

    def _parse_think_content(self, raw: str, finish_reason) -> list[ModelStreamEvent]:
        """有状态地剥离并切分思维链内容。
        因为有些大模型喜欢把思维链装在 `<think>...</think>` 里混在最终回答里吐出来。这个函数会像剥洋葱一样，把夹在中间的思考段落切成 `thinking_delta` 事件吐给前端，把后面的正常回答切成 `delta` 事件吐出来。

        需要拿到的东西：
        - raw (str): 当前这轮刚从网线里捞出来的原始字块文本。
        - finish_reason: 这一轮流式结束的原因。

        会给出来的结果：
        - list[ModelStreamEvent]: 精准解析划分后的流式事件列表（告诉前端哪些是想，哪些是答）。
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
        """将单次流式网络返回的零碎碎片，智能包装成前端能识别的标准数据流事件。
        它会根据不同模型的风格（比如是不是标签形式的 `always_on_style`，还是像某些大模型一样有独立的 reasoning_content 字段）来自动做处理和分类。

        需要拿到的东西：
        - delta (dict): 单次收到的零碎数据碎片字典。
        - finish_reason: 结束原因。

        会给出来的结果：
        - list[ModelStreamEvent]: 精美包装好的标准流式事件列表。
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
        """【非流式同步调用接口】。
        一口气把所有的聊天历史和工具选项打包发给大模型，然后一直在那里等着，直到大模型想完整了、把答案一次性全部吐出来之后，这个函数才慢吞吞地返回最终的 ModelResponse 结果包。

        需要拿到的东西：
        - request (ModelRequest): 包含你想对 AI 说的话以及配置参数的请求对象。

        会给出来的结果：
        - ModelResponse: 包含最终 AI 完整答复和 Token 消耗统计的响应结果对象。
        """
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
        """【同步流式调用接口】。
        把请求发出去后，不需要傻等 AI 把长篇大论全写完。这个函数会像挤牙膏或者像打字机一样，大模型吐出来一个字或一个事件，它就通过 `yield` 立马给你递出来一个流式事件，适合命令行或者传统的同步流展示。

        需要拿到的东西：
        - request (ModelRequest): 包含你想对 AI 说的话的请求对象。

        会给出来的结果：
        - Iterator[ModelStreamEvent]: 一个可以不断迭代取出流式小事件的生成器。
        """

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

    async def async_stream_generate(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        """【异步流式调用接口】。
        这是在 Web 网页后端最常用、最高效的接口。它使用 `httpx` 异步客户端向大模型发请求，大模型吐出来一个字，它就用异步生成器给前端 `yield` 递出去。由于中途等待大模型码字时使用的是极其轻量的 `await` 挂起，在此期间整个系统的 CPU 可以去做别的事情（比如并发响应其他用户的网页请求），实现极高的吞吐性能。

         need拿到的东西：
        - request (ModelRequest): 包含你想对 AI 说的话的请求对象。

        会给出来的结果：
        - AsyncIterator[ModelStreamEvent]: 一个可以被异步循环（async for）不断读取出流式事件的异步生成器。
        """
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
