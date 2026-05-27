"""基础设施层 (Infrastructure Layer) - Tavily 网络搜索工具

职责：
1. 调用 Tavily HTTP API 发起外部互联网的资料检索。
2. 获取搜索到的核心网页内容及参考链接。

不负责：
1. 搜索结果与系统提示词的整合编排。

数据流向：
- 输入：搜索关键词字符串。
- 输出：匹配到的互联网内容片段与参考 URL 列表。
- 上游来源：应用层工具执行模块。
- 下游流向：外部互联网 Tavily 物理 API。
"""

import os,httpx,json
from agent_prototype.tools.protocol import ToolDefinition,RiskLevel
from agent_prototype.model.types.domain import ToolResult

def web_search(query:str,num_results:int=5)->ToolResult:
    """输入：搜索词、结果数量。输出：搜索结果列表的 ToolResult。"""
    
    api_key=os.environ.get("WEB_SEARCH_API_KEY")

    if not api_key:
        return ToolResult(ok=False,content="WEB_SEARCH_API_KEY 未配置",metadata={"tool_name":"web_search"})


    try:
        response = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "max_results": num_results,
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        return ToolResult(ok=True,content = json.dumps(results, ensure_ascii=False),metadata={"tool_name":"web_search"})
    except Exception as exc:
        return ToolResult(ok=False, content=f"搜索失败: {exc}", metadata={"tool_name": "web_search"})
    

WEB_SEARCH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "当你信息不足，需要从网络上获取最新信息时调用",  # 一句话告诉 LLM 什么时候用这个工具
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "具体需要查询的信息",
                },
                "num_results": {
                    "type": "integer",
                    "description": "返回的最大条数",
                    "default": 5,
                    "maximum": 10,
                },
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
}

def build_web_search_tool_definition() -> ToolDefinition:
    """输入：无。输出：web_search 对应的 ToolDefinition。"""
    return ToolDefinition(
        name="web_search",
        schema=WEB_SEARCH_TOOL_SCHEMA,
        handler=web_search,
        risk_level=RiskLevel.SAFE,
    )