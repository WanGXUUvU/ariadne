"""基础设施层 (Infrastructure Layer) - 文件系统物理读取工具

from agent_prototype.tools.types import RiskLevel
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
from agent_prototype.tools.types import ToolDefinition  # 导入工具定义
from agent_prototype.tools.types import RiskLevel


def read_file(path: str, __context__=None) -> str:
    """这是"读取文件内容"的具体执行函数。
    （读取优先查 VFS 暂存区，命中则直接返回；没有命中才降级读物理磁盘。）
    """
    # 🟢 优先检查 VFS 暂存区（可能有本次 Run 中其他工具刚暂存的新内容）
    vfs = None
    if __context__ is not None:
        vfs = __context__.vfs
    if vfs is not None:
        try:
            # 🟢 委托给 VFS 处理：命中返回暂存内容，标记删除则抛 FileNotFoundError，未暂存则降级读磁盘
            return vfs.read_text(path)
        except FileNotFoundError as exc:
            raise ValueError(f"File not found: {path}") from exc
    # 🔴 降级：没有 VFS，走原有的物理磁盘读取逻辑
    target = Path(path)
    if not target.exists():
        raise ValueError(f"File not found: {path}")
    if not target.is_file():
        raise ValueError(f"Not a file: {path}")
    return target.read_text(encoding="utf-8")

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
