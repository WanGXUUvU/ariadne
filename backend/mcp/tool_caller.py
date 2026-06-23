from mcp.types import TextContent

from backend.mcp.mcp_manager import get_mcp_server_manager
from backend.tools.result_types import ToolError, ToolResult


def _get_result_text(result) -> str:
    """从 MCP 原始结果中提取统一的文本内容。"""
    parts = []

    for item in result.content:
        if isinstance(item, TextContent):
            parts.append(item.text)
        else:
            parts.append(str(item))

    if parts:
        return "\n".join(parts)

    if result.structuredContent is not None:
        return str(result.structuredContent)

    return ""


def run_mcp_tool(
    server_id: str,
    remote_tool_name: str,
    args: dict,
) -> ToolResult:
    """同步执行一条 MCP 工具调用，并包装成系统统一结果。"""
    mcp_server_manager = get_mcp_server_manager()

    try:
        result = mcp_server_manager.call_tool(
            server_id,
            remote_tool_name,
            args,
        )

        if result.isError:
            return ToolResult(
                ok=False,
                error=ToolError(
                    code="mcp_tool_error",
                    tool_name=f"mcp.{server_id}.{remote_tool_name}",
                    message=_get_result_text(result) or "MCP tool returned error",
                ),
                metadata={
                    "source_type": "mcp",
                    "server_id": server_id,
                    "remote_tool_name": remote_tool_name,
                },
            )

        return ToolResult(
            ok=True,
            content=_get_result_text(result),
            metadata={
                "source_type": "mcp",
                "server_id": server_id,
                "remote_tool_name": remote_tool_name,
            },
        )
    except Exception as exc:
        return ToolResult(
            ok=False,
            error=ToolError(
                code="mcp_runtime_error",
                tool_name=f"mcp.{server_id}.{remote_tool_name}",
                message=str(exc),
            ),
            metadata={
                "source_type": "mcp",
                "server_id": server_id,
                "remote_tool_name": remote_tool_name,
            },
        )
