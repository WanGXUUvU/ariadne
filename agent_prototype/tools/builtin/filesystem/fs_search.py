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

from agent_prototype.tools.types import ToolDefinition,RiskLevel
from pathlib import Path

def search_text(query: str, path: str = ".") -> str:  # 在目录里搜索文本
    """这是“全文检索”的具体执行函数。
    就像你在整个项目文件夹里按快捷键 `Ctrl+Shift+F`（或者用命令 `grep`），输入你想找的字，它就会掘地三尺，把指定文件夹底下所有文本文件里的每一行都翻个遍，只要发现哪一行提到了你的字，就赶紧把“文件名 + 第几行 + 这一行的内容”通通记下来报给你。

    需要拿到的东西：
    - query (str): 你想搜索的关键字。
    - path (str, 默认 "."): 你想在哪个文件夹里开始搜（不填默认当前运行目录）。

    会给出来的结果：
    - str: 一个大长串文字，每行代表一个匹配结果，例如 `foo.txt:15: 这里包含关键字`。如果没有匹配项，就会温柔地告诉你没找着。
    """
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

def build_search_text_definition() -> ToolDefinition:
    """把上面的“全文检索”工具打包加工，返回一个可供 AI 直接调用和注册的工具定义对象。

    会给出来的结果：
    - ToolDefinition: 打包好、带安全等级的工具定义对象。
    """
    return ToolDefinition(
        name="search_text",
        schema=SEARCH_TEXT_SCHEMA,
        handler=search_text,
        risk_level=RiskLevel.SAFE
    )
