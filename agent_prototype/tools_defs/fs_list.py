from ..core.tool_types import ToolDefinition

from pathlib import Path

def list_dir(path:str)->str:
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
    return ToolDefinition(
        name="list_dir",
        schema=LIST_DIR_SCHEMA,
        handler=list_dir,
    )
