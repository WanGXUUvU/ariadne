"""基础设施层 (Infrastructure Layer) - 文件系统物理读取工具

职责：
1. 执行具体的本地磁盘文件读取操作，获取全部文本内容。

不负责：
1. 路径的安全性验证及物理隔离。

数据流向：
- 输入：绝对文件路径。
- 输出：文件完整文本内容。
- 上游来源：经安全中间件校验后的 Tool 调用。
- 下游流向：操作系统物理磁盘。
"""

from pathlib import Path  # 方便处理文件路径
from agent_prototype.tools.protocol import ToolDefinition,RiskLevel  # 导入工具定义


def read_file(path: str) -> str:  # 真正读文件的函数
    """这是“读取文件内容”的具体执行函数。
    就像你在电脑上双击用记事本打开一个文件查看里面的字，这个函数会把指定路径的文本文件以 UTF-8 编码读取出来，原封不动地交给你。

    需要拿到的东西：
    - path (str): 你想要读取的文件在电脑上的物理绝对路径。

    会给出来的结果：
    - str: 文件的完整文本内容。如果文件不存在或者它根本不是一个普通文件，它会大声报错通知你。
    """
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
    """把上面的“读取文件内容”工具打包加工，返回一个可供 AI 直接调用和注册的工具定义对象。

    会给出来的结果：
    - ToolDefinition: 打包好、带安全等级的工具定义对象。
    """
    return ToolDefinition(
        name="read_file",  # 工具名
        schema=READ_FILE_SCHEMA,  # schema
        handler=read_file,  # 真正执行逻辑
        risk_level=RiskLevel.SAFE,
    )
