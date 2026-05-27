"""基础设施层 (Infrastructure Layer) - 文件系统物理目录列表工具

职责：
1. 执行具体的本地磁盘文件夹目录列表遍历，列出子目录和文件属性。

不负责：
1. 路径越界的沙箱拦截或物理安全防范。

数据流向：
- 输入：绝对文件夹路径。
- 输出：物理文件和子目录列表。
- 上游来源：经安全中间件校验后的 Tool 调用。
- 下游流向：操作系统本地文件系统。
"""

from agent_prototype.tools.protocol import ToolDefinition,RiskLevel

from pathlib import Path

def list_dir(path:str)->str:
    """输入：目录路径字符串。输出：该目录下子项名称组成的换行文本。"""
    target=Path(path)

    if not target.exists():
        raise ValueError(f"Directory not found :{path}")
    
    if not target.is_dir():
        raise ValueError(f"Not a directory: {path}")
    items = sorted(child.name for child in target.iterdir())
    return "\n".join(items)

LIST_DIR_SCHEMA = {  # 给模型看的工具说明
    "type": "function",
    "function": {
        "name": "list_dir",
        "description": "List files and folders in a directory",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list",
                }
            },
            "required": ["path"],
            "additionalProperties": False,
        },
    },
}


def build_list_dir_definition()->ToolDefinition:
    """输入：无。输出：list_dir 对应的 ToolDefinition。"""
    return ToolDefinition(
        name="list_dir",
        schema=LIST_DIR_SCHEMA,
        handler=list_dir,
        risk_level=RiskLevel.SAFE,
    )
