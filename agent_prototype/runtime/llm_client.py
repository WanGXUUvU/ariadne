import os
import requests

BASE_URL = "https://token.sensenova.cn/v1"
MODEL = "deepseek-v4-flash"

def call_llm(messages,tools=None):
    """输入：消息列表、可选工具 schema 列表。输出：LLM 返回的完整 assistant message 字典。"""
    # 这里返回完整的 assistant message，而不是只返回 content。
    # 这样上层才能判断模型有没有发出 tool_calls。
    api_key = os.environ.get("SENSENOVA_API_KEY")
    if not api_key:
        raise RuntimeError("Missing SENSENOVA_API_KEY")
    url=f"{BASE_URL}/chat/completions"
    headers ={
        "Accept":"application/json",
        "Authorization":f"Bearer {api_key}",
        "Content-Type":"application/json"
    }
    payload={
        "model":MODEL,
        "messages":messages,
        "thinking": {"type": "disabled"},
    }

    if tools:
        payload["tools"]=tools
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    if not response:
        print("STATUS:",response.status_code)
        print("BODY:",response.text)    
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
