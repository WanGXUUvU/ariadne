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

def web_search(query: str, num_results: int = 5) -> ToolResult:
    """这是“网页搜索引擎”的具体执行函数。
    当你想查一下最新的新闻、最新的代码库用法，或者 AI 的知识库不够新时，这个工具会飞快地跑去 Tavily 搜索引擎发起网络搜索，把查到的核心网页文本和参考链接原封不动拉回来给你看。

    需要拿到的东西：
    - query (str): 你想在网上搜索什么词。
    - num_results (int, 默认 5): 你最多想要几个搜索结果（一般最多能拿 10 个）。

    会给出来的结果：
    - ToolResult: 一个搜索结果包裹。如果成功，`content` 里就是一串 JSON 文本，包含查到的所有网页标题、正文片段和 URL；如果失败了（比如你忘了在环境变量里配 API Key 或者网络断了），它会返回 False 并给出原因。
    """
    
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
    """把上面的“网页搜索引擎”工具打包加工，返回一个可供 AI 直接调用和注册的工具定义对象。

    会给出来的结果：
    - ToolDefinition: 打包好、带安全等级的工具定义对象。
    """
    return ToolDefinition(
        name="web_search",
        schema=WEB_SEARCH_TOOL_SCHEMA,
        handler=web_search,
        risk_level=RiskLevel.SAFE,
    )