from backend.mcp.mcp_manager import McpToolInfo
from backend.mcp.tool_caller import run_mcp_tool
from backend.tools.types import RiskLevel, ToolDefinition


def build_mcp_tool_schema(mcp_tool: McpToolInfo) -> dict:
    """把内部 MCP 工具信息转换成模型可见的 function schema。"""
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.internal_tool_name,
            "description": mcp_tool.description or "",
            "parameters": mcp_tool.input_schema,
        },
    }


def build_mcp_tool_definition(
    mcp_tool: McpToolInfo,
) -> ToolDefinition:
    """把一条 MCP 工具描述绑定成系统内部 ToolDefinition。"""
    def handler(__context__=None, **kwargs):
        return run_mcp_tool(
            mcp_tool.server_id,
            mcp_tool.remote_tool_name,
            kwargs,
        )

    return ToolDefinition(
        name=mcp_tool.internal_tool_name,
        schema=build_mcp_tool_schema(mcp_tool),
        handler=handler,
        risk_level=RiskLevel.SAFE,
    )


def build_mcp_tool_definitions(
    mcp_tools: list[McpToolInfo],
) -> list[ToolDefinition]:
    """批量把 MCP 工具描述转换成可注册的 ToolDefinition。"""
    return [build_mcp_tool_definition(mcp_tool) for mcp_tool in mcp_tools]
