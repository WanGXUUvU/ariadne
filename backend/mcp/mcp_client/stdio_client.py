from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from datetime import timedelta
from mcp.types import CallToolResult

from backend.mcp.types import StdioMcpServerConfig


class StdioMcpClient:
    """用官方 SDK 连接 stdio MCP server。"""

    def __init__(self, config: StdioMcpServerConfig) -> None:
        """保存 server 配置，并初始化连接期状态。"""
        self.config = config
        self._session: ClientSession | None = None
        self._stdio_cm = None
        self._read = None
        self._write = None

    async def connect(self) -> None:
        """启动子进程传输，并完成 MCP initialize 握手。"""
        server = StdioServerParameters(
            command=self.config.command,
            args=self.config.args,
            env=dict(self.config.env),
            cwd=self.config.cwd,
        )
        self._stdio_cm = stdio_client(server)
        self._read, self._write = await self._stdio_cm.__aenter__()

        session = ClientSession(self._read, self._write)
        self._session = await session.__aenter__()
        await self._session.initialize()

    async def list_tools(self):
        """读取远端 server 暴露的工具列表。"""
        if self._session is None:
            raise RuntimeError("MCP session not connected")
        return await self._session.list_tools()

    async def close(self) -> None:
        """关闭 MCP session 和 stdio transport。"""
        if self._session is not None:
            await self._session.__aexit__(None, None, None)
            self._session = None

        if self._stdio_cm is not None:
            await self._stdio_cm.__aexit__(None, None, None)
            self._stdio_cm = None

    async def call_tool(
        self,
        remote_tool_name: str,
        arguments: dict | None = None,
    ) -> CallToolResult:
        """调用远端工具，并按配置传入读取超时。"""
        if self._session is None:
            raise RuntimeError("MCP session not connected")

        return await self._session.call_tool(
            name=remote_tool_name,
            arguments=arguments or {},
            read_timeout_seconds=timedelta(seconds=self.config.tool_timeout_sec),
        )
