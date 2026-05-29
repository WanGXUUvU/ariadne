"""基础设施层 (Infrastructure Layer) - 文件系统物理写入工具

from agent_prototype.tools.types import RiskLevel
职责：
1. 实现具体的本地磁盘物理文件系统写入操作。
2. 保证文件写入操作的物理事务完整。

不负责：
1. 任何安全越界过滤（安全越界检测必须由 SandboxPathInterceptor 拦截器在上层进行）。

数据流向：
- 输入：物理目标绝对路径、待写入的文本内容。
- 输出：物理写入结果状态。
- 上游来源：经安全中间件校验后的 Tool 调用。
- 下游流向：物理操作系统磁盘存储。
"""

from pathlib import Path  # 处理文件路径
from agent_prototype.tools.types import ToolDefinition  # 导入工具定义
from agent_prototype.tools.types import RiskLevel


def write_file(path: str, content: str) -> str:  # 把内容写入文件
    """这是“把文字写入文件”的具体执行函数。
    就像你在电脑上新建或者打开一个文本文件，把一堆字粘贴进去然后点击“保存”。如果存放这个文件的文件夹根本不存在，它还会很贴心地自动把缺失的文件夹全都建好。

    需要拿到的东西：
    - path (str): 你想要写入的目标文件物理绝对路径。
    - content (str): 想要写进文件里的具体文本内容。

    会给出来的结果：
    - str: 一个写入结果的通知，比如告诉你成功往哪个文件写入了多少个字符。如果指定的路径其实是一个文件夹，它会明智地拒绝并报错。
    """
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
    """把上面的“把文字写入文件”工具打包加工，返回一个可供 AI 直接调用和注册的工具定义对象。

    会给出来的结果：
    - ToolDefinition: 打包好、带安全等级的工具定义对象。由于这个工具涉及修改物理磁盘内容，它的风险等级被定为 WRITE（写操作风险）。
    """
    return ToolDefinition(
        name="write_file",  # 工具名
        schema=WRITE_FILE_SCHEMA,  # schema
        handler=write_file,  # 真正执行函数
        risk_level=RiskLevel.WRITE,
    )
