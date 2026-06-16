from backend.infra.config.settings import load_settings, save_settings

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
