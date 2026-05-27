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

def list_dir(path: str) -> str:
    """
    大白话解释：
    这是“列出文件夹内容”的具体执行函数。
    就像你在电脑上双击打开一个文件夹，或者在命令行打 `ls` / `dir`，它会把你指定文件夹底下的所有文件和子文件夹名字按字母顺序排好，用换行符连成一大串文字拿给你看。

    需要拿到的东西：
    - path (str): 你想要查看的文件夹绝对路径。

    会给出来的结果：
    - str: 包含该目录下所有子文件和子文件夹名称的换行文本。如果路径找不到或者它根本不是一个文件夹，就会气呼呼地抛出报错。
    """
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


def build_list_dir_definition() -> ToolDefinition:
    """
    大白话解释：
    把上面的“列出文件夹内容”工具打包加工，返回一个可供 AI 直接调用和注册的工具定义对象。

    会给出来的结果：
    - ToolDefinition: 打包好、带安全等级的工具定义对象。
    """
    return ToolDefinition(
        name="list_dir",
        schema=LIST_DIR_SCHEMA,
        handler=list_dir,
        risk_level=RiskLevel.SAFE,
    )
