import asyncio
from dataclasses import dataclass
from threading import Event, Thread
from typing import Any

from mcp.types import Tool

from backend.mcp.mcp_client.stdio_client import StdioMcpClient
from backend.mcp.mcp_client.streamable_http_client import StreamableHttpMcpClient
from backend.mcp.settings import load_mcp_server_config
from backend.mcp.types import (
    McpServerConfig,
    McpTranSport,
    StdioMcpServerConfig,
    StreamableHttpMcpServerConfig,
)

@dataclass(frozen=True)
class McpToolInfo:
    """系统内部保存的 MCP 工具元数据。"""

    server_id: str
    remote_tool_name: str
    internal_tool_name: str
    title: str | None
    description: str | None
    input_schema: dict
    output_schema: dict | None


@dataclass
class ConnectedMcpServer:
    """一台已经连上的 MCP server 及其工具缓存。"""

    config: McpServerConfig
    client: StdioMcpClient | StreamableHttpMcpClient
    tools: list[McpToolInfo]


def build_mcp_tool_info(
    config: McpServerConfig,
    tool: Tool,
) -> McpToolInfo:
    """把 SDK 原始 Tool 转成系统内部的 McpToolInfo。"""
    return McpToolInfo(
        server_id=config.sever_id,
        remote_tool_name=tool.name,
        internal_tool_name=f"mcp.{config.sever_id}.{tool.name}",
        title=tool.title,
        description=tool.description,
        input_schema=tool.inputSchema,
        output_schema=tool.outputSchema,
    )


class McpRuntimeThread:
    """单独承载 MCP async runtime 的后台线程。"""

    def __init__(self) -> None:
        """初始化后台线程和 event loop 相关状态。"""
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: Thread | None = None
        self._loop_ready = Event()

    def _run_loop(self) -> None:
        """在线程内部创建 event loop，并持续运行。"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._loop_ready.set()
        loop.run_forever()

    def start(self) -> None:
        """启动 MCP 专用后台线程，等待 event loop 就绪。"""
        self._thread = Thread(target=self._run_loop, daemon=True, name="mcp-runtime")
        self._thread.start()
        self._loop_ready.wait()

    def run_on_loop(self, coro: Any):
        """把 coroutine 投递到 MCP 专用 loop，并同步等待结果。"""
        if self._loop is None:
            raise RuntimeError("MCP runtime loop not started")

        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def stop(self) -> None:
        """停止后台 loop，并回收线程和 loop 状态。"""
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread is not None:
            self._thread.join(timeout=5)

        if self._loop is not None:
            self._loop.close()

        self._loop = None
        self._thread = None
        self._loop_ready.clear()


class McpServerManager:
    """管理 MCP server 长连接、工具缓存和工具调用。"""

    def __init__(self) -> None:
        """初始化 server 缓存、runtime 和启动状态。"""
        self._servers: dict[str, ConnectedMcpServer] = {}
        self._server_errors: dict[str, str] = {}
        self._runtime = McpRuntimeThread()
        self._started = False

    def _require_started(self) -> None:
        """确保 runtime 已启动，否则直接报错。"""
        if not self._started:
            raise RuntimeError("MCP runtime not started")

    def _build_client(
        self,
        config: McpServerConfig,
    ) -> StdioMcpClient | StreamableHttpMcpClient:
        """按 transport 构造对应的 MCP client。"""
        if config.transport == McpTranSport.STDIO:
            return StdioMcpClient(config)

        if config.transport == McpTranSport.STREAMABLE_HTTP:
            return StreamableHttpMcpClient(config)

        raise ValueError(f"unsupported mcp transport: {config.transport}")

    async def _start_async(self) -> None:
        """连接全部已启用 server，并缓存工具列表。"""
        self._server_errors.clear()

        for config in load_mcp_server_config():
            client = self._build_client(config)

            try:
                await client.connect()
                result = await client.list_tools()
                tools = [build_mcp_tool_info(config, tool) for tool in result.tools]
                self._servers[config.sever_id] = ConnectedMcpServer(
                    config=config,
                    client=client,
                    tools=tools,
                )
                self._server_errors.pop(config.sever_id, None)
            except Exception as exc:
                await client.close()
                self._server_errors[config.sever_id] = str(exc)
                if config.required:
                    raise

                print(
                    f"[MCP] skip server startup: server_id={config.sever_id}, error={exc}"
                )

    async def _stop_async(self) -> None:
        """关闭全部已连接 server，并清空缓存。"""
        for server in self._servers.values():
            await server.client.close()

        self._servers.clear()
        self._server_errors.clear()

    def start(self) -> None:
        """启动 MCP runtime，并在后台 loop 中连接全部 server。"""
        if self._started:
            return

        self._runtime.start()

        try:
            self._runtime.run_on_loop(self._start_async())
        except Exception:
            try:
                self._runtime.run_on_loop(self._stop_async())
            finally:
                self._runtime.stop()
            raise

        self._started = True

    def stop(self) -> None:
        """停止 MCP runtime，并关闭全部长连接。"""
        if not self._started:
            return

        try:
            self._runtime.run_on_loop(self._stop_async())
        finally:
            self._runtime.stop()
            self._started = False

    def is_started(self) -> bool:
        """返回当前 MCP runtime 是否已经启动。"""
        return self._started

    def reload(self) -> None:
        """按最新配置重建 MCP runtime 和全部长连接。"""
        if self._started:
            self.stop()
        self.start()

    def list_all_tools(self) -> list[McpToolInfo]:
        """读取全部已连接 server 的工具缓存。"""
        self._require_started()

        all_tools: list[McpToolInfo] = []
        for server in self._servers.values():
            all_tools.extend(server.tools)
        return all_tools

    async def _call_tool_async(
        self,
        server_id: str,
        remote_tool_name: str,
        args: dict,
    ):
        """在 MCP 专用 loop 中执行一条远端工具调用。"""
        server = self._servers.get(server_id)
        if server is None:
            raise ValueError(f"unknown mcp server: {server_id}")

        return await server.client.call_tool(remote_tool_name, args)

    def call_tool(self, server_id: str, remote_tool_name: str, args: dict):
        """同步入口：复用长连接调用远端 MCP 工具。"""
        self._require_started()
        return self._runtime.run_on_loop(
            self._call_tool_async(server_id, remote_tool_name, args)
        )

    def get_runtime_snapshot(self) -> dict[str, dict]:
        """返回当前已连接 server 和失败 server 的运行时摘要。"""
        if not self._started:
            return {}

        snapshot: dict[str, dict] = {}
        for server_id, server in self._servers.items():
            snapshot[server_id] = {
                "runtime_status": "connected",
                "tool_count": len(server.tools),
                "last_error": None,
            }

        for server_id, message in self._server_errors.items():
            snapshot[server_id] = {
                "runtime_status": "error",
                "tool_count": 0,
                "last_error": message,
            }

        return snapshot


_mcp_server_manager = McpServerManager()


def get_mcp_server_manager() -> McpServerManager:
    """返回进程级 MCP manager 单例。"""
    return _mcp_server_manager
