"""基础设施层 (Infrastructure Layer) - 测试回显工具

from agent_prototype.tools.result_types import ToolResult
from agent_prototype.tools.types import RiskLevel
职责：
1. 内置的回显（Echo）物理工具，直接返回用户传入的内容，用于系统连通性与参数流传走通。
2. 提供测试工具标准的 Pydantic 入参模型。

不负责：
1. 安全拦截或物理越界检测。

数据流向：
- 输入：入参字符串。
- 输出：相同内容的回显数据。
- 上游来源：Application 运行时调用驱动。
- 下游流向：大模型或前端消息面板。
"""

from agent_prototype.tools.types import ToolDefinition
from agent_prototype.tools.result_types import ToolResult
from agent_prototype.tools.types import RiskLevel


def echo_tool(text: str) -> ToolResult:
    """这是“回声（Echo）工具”的具体执行函数。
    它其实就像是一个传声筒或者山谷里的回音，你喂给它一段文字，它就会原封不动地在前头加个“我收到啦：”的标识，然后把这段话回传给你。这主要是用来测试系统是不是跑通了、工具调用的链路是不是正常的。

    需要拿到的东西：
    - text (str): 你想让它复读的那段文字。

    会给出来的结果：
    - ToolResult: 一个回显成功的包裹，里面就是你给的文字前面加上了 `tool received:`。
    """
    # 这是本地真正执行的工具逻辑。
    # 模型只会返回 tool_calls，真正的函数执行发生在这里。
    return ToolResult(
        ok=True,
        content=f"tool received:{text}",
        metadata={"tool_name": "echo_tool"},
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
    """把上面的“回声（Echo）工具”打包加工，返回一个可供 AI 直接调用和注册的工具定义对象。

    会给出来的结果：
    - ToolDefinition: 打包好、带安全等级的工具定义对象。
    """
    return ToolDefinition(
        name="echo_tool",  # 工具名
        schema=ECHO_TOOL_SCHEMA,  # schema
        handler=echo_tool,  # 执行函数
        risk_level=RiskLevel.SAFE,
    )
