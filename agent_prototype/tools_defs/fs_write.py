from pathlib import Path  # 处理文件路径

from ..tool_types import ToolDefinition  # 导入工具定义


def write_file(path: str, content: str) -> str:  # 把内容写入文件
    target = Path(path)  # 把字符串路径转成 Path 对象

    if target.exists() and target.is_dir():  # 如果路径已经存在，而且是目录
        raise ValueError(f"Path is a directory: {path}")  # 明确报错，不能往目录里写文本

    if target.parent and not target.parent.exists():  # 如果父目录不存在
        target.parent.mkdir(parents=True, exist_ok=True)  # 自动创建父目录

    target.write_text(content, encoding="utf-8")  # 以 UTF-8 写入文本
    return f"Wrote {len(content)} chars to {path}"  # 返回写入结果摘要


WRITE_FILE_SCHEMA = {  # 给模型看的工具说明
    "type": "function",
    "function": {
        "name": "write_file",  # 工具名
        "description": "Write text content to a file",  # 工具描述
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to write",
                },
                "content": {
                    "type": "string",
                    "description": "Text content to write into the file",
                },
            },
            "required": ["path", "content"],  # 两个参数都必填
            "additionalProperties": False,  # 不允许多余参数
        },
    },
}


def build_write_file_tool_definition() -> ToolDefinition:  # 构造 registry 需要的工具对象
    return ToolDefinition(
        name="write_file",  # 工具名
        schema=WRITE_FILE_SCHEMA,  # schema
        handler=write_file,  # 真正执行函数
    )
