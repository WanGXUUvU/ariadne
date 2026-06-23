from datetime import timedelta
import os

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult

from backend.mcp.types import StreamableHttpMcpServerConfig


class StreamableHttpMcpClient:
    """用官方 SDK 连接 streamable_http MCP server。"""

    def __init__(self, config: StreamableHttpMcpServerConfig) -> None:
        """保存 server 配置，并初始化连接期状态。"""
        self.config = config
        self._session: ClientSession | None = None
        self._http_client: httpx.AsyncClient | None = None
        self._http_cm = None
        self._read = None
        self._write = None
        self._get_session_id = None

    def _build_headers(self) -> dict[str, str]:
        """把静态 headers、环境变量 headers 和 bearer token 合并成请求头。"""
        headers = dict(self.config.http_headers)

        for header_name, env_var_name in self.config.env_http_headers.items():
            env_value = os.getenv(env_var_name)
            if env_value is None:
                raise ValueError(
                    f"missing environment variable for header {header_name}: {env_var_name}"
                )
            headers[header_name] = env_value

        if self.config.bearer_token_env_var:
            token = os.getenv(self.config.bearer_token_env_var)
            if token is None:
                raise ValueError(
                    f"missing bearer token environment variable: {self.config.bearer_token_env_var}"
                )
            headers["Authorization"] = f"Bearer {token}"

        return headers

    async def connect(self) -> None:
        """建立 HTTP 传输和 MCP session，并完成 initialize 握手。"""
        timeout = httpx.Timeout(
            self.config.startup_timeout_sec,
            read=self.config.tool_timeout_sec,
        )
        self._http_client = httpx.AsyncClient(
            timeout=timeout,
            headers=self._build_headers(),
        )
        self._http_cm = streamable_http_client(
            self.config.url,
            http_client=self._http_client,
        )
        self._read, self._write, self._get_session_id = await self._http_cm.__aenter__()

        session = ClientSession(self._read, self._write)
        self._session = await session.__aenter__()
        await self._session.initialize()

    async def list_tools(self):
        """读取远端 server 暴露的工具列表。"""
        if self._session is None:
            raise RuntimeError("MCP session not connected")
        return await self._session.list_tools()

    async def close(self) -> None:
        """关闭 MCP session、HTTP transport 和底层 HTTP client。"""
        if self._session is not None:
            await self._session.__aexit__(None, None, None)
            self._session = None

        if self._http_cm is not None:
            await self._http_cm.__aexit__(None, None, None)
            self._http_cm = None

        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

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
