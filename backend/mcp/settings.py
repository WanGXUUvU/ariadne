from backend.infra.config.settings import load_settings, save_settings
from backend.mcp.types import (
    StdioMcpServerConfig,
    StreamableHttpMcpServerConfig,
    McpTranSport,
)


def get_mcp_servers() -> list:
    """从 settings.json 中获取已配置的 MCP servers 列表"""
    return load_settings().get("mcp", {}).get("servers", [])


def save_mcp_servers(servers: list) -> None:
    """将 MCP servers 列表保存回 settings.json"""
    settings = load_settings()
    if "mcp" not in settings:
        settings["mcp"] = {}
    settings["mcp"]["servers"] = servers
    save_settings(settings)


def build_mcp_server_config(
    raw_config: dict,
) -> StdioMcpServerConfig | StreamableHttpMcpServerConfig:
    """把单条原始配置转换成内部的 MCP 配置对象。"""
    sever_id = raw_config.get("server_id")
    if not sever_id:
        raise ValueError("missing server_id")

    display_name = raw_config.get("display_name")
    transport = raw_config.get("transport")
    enable = raw_config.get("enabled", True)
    required = raw_config.get("required", False)
    startup_timeout_sec = raw_config.get("startup_timeout_sec", 10)
    tool_timeout_sec = raw_config.get("tool_timeout_sec", 30)

    if transport == "stdio":
        command = raw_config.get("command")
        if not command:
            raise ValueError(f"server {sever_id}: stdio server missing command")

        return StdioMcpServerConfig(
            sever_id=sever_id,
            display_name=display_name,
            transport=McpTranSport.STDIO,
            enable=enable,
            required=required,
            startup_timeout_sec=startup_timeout_sec,
            tool_timeout_sec=tool_timeout_sec,
            command=command,
            args=raw_config.get("args", []),
            env=raw_config.get("env", {}),
            cwd=raw_config.get("cwd"),
        )

    if transport == "streamable_http":
        url = raw_config.get("url")
        if not url:
            raise ValueError(f"server {sever_id}: streamable_http server missing url")

        return StreamableHttpMcpServerConfig(
            sever_id=sever_id,
            display_name=display_name,
            transport=McpTranSport.STREAMABLE_HTTP,
            enable=enable,
            required=required,
            startup_timeout_sec=startup_timeout_sec,
            tool_timeout_sec=tool_timeout_sec,
            url=url,
            bearer_token=raw_config.get("bearer_token"),
            http_headers=raw_config.get("http_headers", {}),
        )

    raise ValueError(f"server {sever_id}: unsupported transport {transport}")


def load_all_mcp_server_configs() -> list[
    StreamableHttpMcpServerConfig | StdioMcpServerConfig
]:
    """加载全部 MCP server 配置，不区分启用状态。"""
    configs = []
    mcp_servers = get_mcp_servers()
    for mcp_server in mcp_servers:
        mcp_config = build_mcp_server_config(mcp_server)
        configs.append(mcp_config)
    return configs


def load_mcp_server_config() -> list[
    StreamableHttpMcpServerConfig | StdioMcpServerConfig
]:
    """加载全部已启用的 MCP server 配置。"""
    configs = []
    for mcp_config in load_all_mcp_server_configs():
        if mcp_config.enable:
            configs.append(mcp_config)
    return configs


def load_enabled_stdio_server_configs() -> list[StdioMcpServerConfig]:
    """筛出全部已启用的 stdio server 配置。"""
    configs = []
    for config in load_mcp_server_config():
        if isinstance(config, StdioMcpServerConfig):
            configs.append(config)
    return configs


def load_enabled_streamable_http_server_configs() -> list[StreamableHttpMcpServerConfig]:
    """筛出全部已启用的 streamable_http server 配置。"""
    configs = []
    for config in load_mcp_server_config():
        if isinstance(config, StreamableHttpMcpServerConfig):
            configs.append(config)
    return configs
