import os
import requests 

BASE_URL = "https://api.bltcy.ai"
API_KEY = "sk-if5ozW27udBQVVuHtRKoALsbc4Ob0qu7RxEaDGLniCIGVr1U"
MODEL = "MiniMax-M2.5-lightning"


def call_llm(messages,tools=None):
    # 这里返回完整的 assistant message，而不是只返回 content。
    # 这样上层才能判断模型有没有发出 tool_calls。
    url=f"{BASE_URL}/v1/chat/completions"
    headers ={
        "Accept":"application/json",
        "Authorization":f"Bearer {API_KEY}",
        "Content-Type":"application/json"
    }
    payload={
        "model":MODEL,
        "messages":messages,
    }

    if tools:
        payload["tools"]=tools
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]

# 期望返回的结构大致是：
# {
#   "role": "assistant",
#   "content": None,
#   "tool_calls": [
#     {
#       "id": "call_001",
#       "type": "function",
#       "function": {
#         "name": "echo_tool",
#         "arguments": "{\"text\":\"hello\"}"
#       }
#     }
#   ]
# }
