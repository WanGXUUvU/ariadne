"""基础设施层 (Infrastructure Layer) - 文件系统文本检索工具

职责：
1. 提供本地磁盘物理文件系统的搜索与正则匹配功能。
2. 对指定目录下的内容进行文本检索，返回匹配的位置及片段。

不负责：
1. 沙箱安全边界防范与路径真实性检测。

数据流向：
- 输入：绝对目录路径、搜索关键字和匹配参数。
- 输出：匹配结果文件与片段列表。
- 上游来源：经安全中间件校验后的 Tool 调用。
- 下游流向：操作系统文件系统。
"""

from agent_prototype.tools.protocol import ToolDefinition,RiskLevel

from pathlib import Path

def search_text(query: str, path: str = ".") -> str:  # 在目录里搜索文本
    """输入：搜索关键字、可选目录路径。输出：匹配结果文本或无匹配提示。"""
    target = Path(path)  # 把字符串路径转成 Path 对象

    if not target.exists():  # 如果路径不存在
        raise ValueError(f"Path not found: {path}")  # 明确报错

    if not target.is_dir():  # 如果不是目录
        raise ValueError(f"Not a directory: {path}")  # 明确报错

    matches = []  # 保存所有匹配结果

    for file_path in target.rglob("*"):  # 递归遍历目录下所有文件
        if not file_path.is_file():  # 如果不是文件就跳过
            continue  # 继续下一个条目

        try:  # 尝试按文本读取
            content = file_path.read_text(encoding="utf-8")  # 读取文件内容
        except UnicodeDecodeError:  # 如果不是文本文件
            continue  # 跳过二进制或乱码文件

        for line_no, line in enumerate(content.splitlines(), start=1):  # 按行搜索
            if query in line:  # 如果这一行包含关键字
                matches.append(f"{file_path}:{line_no}: {line.strip()}")  # 记录匹配结果

    return "\n".join(matches) if matches else f"No matches for: {query}"  # 返回结果或空提示


SEARCH_TEXT_SCHEMA = {  # 给模型看的工具说明
    "type": "function",
    "function": {
        "name": "search_text",  # 工具名
        "description": "Search text in files under a directory",  # 工具描述
        "parameters": {
            "type": "object",
            "properties": {
                "query": {  # 搜索关键字
                    "type": "string",
                    "description": "Text to search for",
                },
                "path": {  # 搜索目录
                    "type": "string",
                    "description": "Directory path to search in",
                    "default": ".",
                },
            },
            "required": ["query"],  # query 必填
            "additionalProperties": False,  # 不允许多余参数
        },
    },
}

def build_search_text_definition()->ToolDefinition:
    """输入：无。输出：search_text 对应的 ToolDefinition。"""
    return ToolDefinition(
        name="search_text",
        schema=SEARCH_TEXT_SCHEMA,
        handler=search_text,
        risk_level=RiskLevel.SAFE
    )
