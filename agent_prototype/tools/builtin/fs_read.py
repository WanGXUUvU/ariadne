from pathlib import Path  # 方便处理文件路径

from ...core.tool_types import ToolDefinition,RiskLevel  # 导入工具定义


def read_file(path: str) -> str:  # 真正读文件的函数
    """输入：文件路径字符串。输出：该文件的 UTF-8 文本内容。"""
    target = Path(path)  # 把字符串路径转成 Path 对象

    if not target.exists():  # 文件不存在
        raise ValueError(f"File not found: {path}")  # 明确报错

    if not target.is_file():  # 路径存在但不是文件
        raise ValueError(f"Not a file: {path}")  # 明确报错

    return target.read_text(encoding="utf-8")  # 读取 UTF-8 文本内容


READ_FILE_SCHEMA = {  # 给模型看的说明
    "type": "function",
    "function": {
        "name": "read_file",
        "description": "Read the content of a file",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file",
                }
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
}


def build_read_file_tool_definition() -> ToolDefinition:  # 构造注册对象
    """输入：无。输出：read_file 对应的 ToolDefinition。"""
    return ToolDefinition(
        name="read_file",  # 工具名
        schema=READ_FILE_SCHEMA,  # schema
        handler=read_file,  # 真正执行逻辑
        risk_level=RiskLevel.SAFE,
    )
