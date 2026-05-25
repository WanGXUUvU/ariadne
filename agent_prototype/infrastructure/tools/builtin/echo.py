from agent_prototype.core.tool_types import ToolDefinition
from agent_prototype.core.schemas import ToolResult
from agent_prototype.core.tool_types import RiskLevel

def echo_tool(text: str) -> ToolResult:
    """输入：文本字符串。输出：回显该文本的 ToolResult。"""
    # 这是本地真正执行的工具逻辑。
    # 模型只会返回 tool_calls，真正的函数执行发生在这里。
    return ToolResult(
        ok=True,
        content=f"tool received:{text}",
        metadata={"tool_name":"echo_tool"},
    )

ECHO_TOOL_SCHEMA = {  # 给模型看的工具说明
    "type": "function",
    "function": {
        "name": "echo_tool",
        "description": "Echo the input text back to the caller",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to echo back.",
                }
            },
            "required": ["text"],
            "additionalProperties": False,
        },
    },
}

def build_echo_tool_definition() -> ToolDefinition:  # 构造注册对象
    """输入：无。输出：echo_tool 对应的 ToolDefinition。"""
    return ToolDefinition(
        name="echo_tool",  # 工具名
        schema=ECHO_TOOL_SCHEMA,  # schema
        handler=echo_tool,  # 执行函数
        risk_level=RiskLevel.SAFE
    )
