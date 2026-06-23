"""MCP 配置应用服务。

职责：
- 管理 settings.json 里的 MCP server 配置 CRUD。
- 读取当前 MCP runtime 状态并拼成前端可用摘要。
- 提供显式 reload 入口，让运行中的 MCP runtime 重新按最新配置启动。
"""

from backend.mcp.mcp_manager import get_mcp_server_manager
from backend.mcp.settings import (
    build_mcp_server_config,
    get_mcp_servers,
    save_mcp_servers,
)


class McpSettingsService:
    """编排 MCP 配置文件和运行时状态。"""

    def _normalize_raw_server(self, raw_server: dict) -> dict:
        """按 transport 产出标准化配置字典，去掉无关字段。"""
        transport = raw_server.get("transport")
        normalized = {
            "server_id": raw_server.get("server_id"),
            "display_name": raw_server.get("display_name"),
            "transport": transport,
            "enabled": raw_server.get("enabled", True),
            "required": raw_server.get("required", False),
            "startup_timeout_sec": raw_server.get("startup_timeout_sec", 10),
            "tool_timeout_sec": raw_server.get("tool_timeout_sec", 30),
        }

        if transport == "stdio":
            normalized["command"] = raw_server.get("command")
            normalized["args"] = raw_server.get("args", [])
            normalized["env"] = raw_server.get("env", {})
            normalized["cwd"] = raw_server.get("cwd")
            return normalized

        if transport == "streamable_http":
            normalized["url"] = raw_server.get("url")
            normalized["bearer_token_env_var"] = raw_server.get("bearer_token_env_var")
            normalized["http_headers"] = raw_server.get("http_headers", {})
            normalized["env_http_headers"] = raw_server.get("env_http_headers", {})
            return normalized

        return normalized

    def _validate_raw_server(self, raw_server: dict) -> dict:
        """用内部配置模型校验一条 server 配置是否合法。"""
        normalized = self._normalize_raw_server(raw_server)
        build_mcp_server_config(normalized)
        return normalized

    def _find_server_index(self, servers: list[dict], server_id: str) -> int:
        """在原始配置列表里按 server_id 查找条目位置。"""
        for index, server in enumerate(servers):
            if server.get("server_id") == server_id:
                return index
        raise LookupError(f"MCP server {server_id} not found")

    def _build_runtime_info(self, raw_server: dict) -> dict:
        """读取当前 manager 里的运行时状态，并映射到列表摘要字段。"""
        enabled = raw_server.get("enabled", True)
        if not enabled:
            return {
                "runtime_status": "disabled",
                "tool_count": 0,
                "last_error": None,
            }

        manager = get_mcp_server_manager()
        if not manager.is_started():
            return {
                "runtime_status": "not_started",
                "tool_count": 0,
                "last_error": None,
            }

        runtime_snapshot = manager.get_runtime_snapshot()
        return runtime_snapshot.get(
            raw_server.get("server_id"),
            {
                "runtime_status": "not_started",
                "tool_count": 0,
                "last_error": None,
            },
        )

    def _build_server_out(self, raw_server: dict) -> dict:
        """把原始配置和 runtime 状态拼成前端响应对象。"""
        normalized = self._validate_raw_server(raw_server)
        runtime_info = self._build_runtime_info(normalized)

        return {
            "server_id": normalized["server_id"],
            "display_name": normalized.get("display_name"),
            "transport": normalized["transport"],
            "enabled": normalized["enabled"],
            "required": normalized["required"],
            "startup_timeout_sec": normalized["startup_timeout_sec"],
            "tool_timeout_sec": normalized["tool_timeout_sec"],
            "command": normalized.get("command"),
            "args": normalized.get("args", []),
            "env": normalized.get("env", {}),
            "cwd": normalized.get("cwd"),
            "url": normalized.get("url"),
            "bearer_token_env_var": normalized.get("bearer_token_env_var"),
            "http_headers": normalized.get("http_headers", {}),
            "env_http_headers": normalized.get("env_http_headers", {}),
            "runtime_status": runtime_info["runtime_status"],
            "tool_count": runtime_info["tool_count"],
            "last_error": runtime_info["last_error"],
        }

    def list_servers(self) -> list[dict]:
        """返回全部 MCP server 摘要列表。"""
        return [self._build_server_out(server) for server in get_mcp_servers()]

    def get_server(self, server_id: str) -> dict:
        """返回单条 MCP server 详情。"""
        servers = get_mcp_servers()
        server_index = self._find_server_index(servers, server_id)
        return self._build_server_out(servers[server_index])

    def create_server(self, payload: dict) -> dict:
        """新增一条 MCP server 配置并保存到 settings.json。"""
        servers = get_mcp_servers()
        server_id = payload.get("server_id")

        for server in servers:
            if server.get("server_id") == server_id:
                raise ValueError(f"MCP server {server_id} already exists")

        normalized = self._validate_raw_server(payload)
        servers.append(normalized)
        save_mcp_servers(servers)
        return self._build_server_out(normalized)

    def patch_server(self, server_id: str, payload: dict) -> dict:
        """局部更新一条 MCP server 配置并保存。"""
        servers = get_mcp_servers()
        server_index = self._find_server_index(servers, server_id)

        merged = dict(servers[server_index])
        merged.update(payload)
        merged["server_id"] = server_id

        normalized = self._validate_raw_server(merged)
        servers[server_index] = normalized
        save_mcp_servers(servers)
        return self._build_server_out(normalized)

    def delete_server(self, server_id: str) -> None:
        """删除一条 MCP server 配置。"""
        servers = get_mcp_servers()
        server_index = self._find_server_index(servers, server_id)
        del servers[server_index]
        save_mcp_servers(servers)

    def reload_runtime(self) -> dict:
        """重启 MCP runtime，并返回本次重载结果摘要。"""
        manager = get_mcp_server_manager()
        manager.reload()

        runtime_snapshot = manager.get_runtime_snapshot()
        errors = []
        connected_servers = 0

        for server_id, info in runtime_snapshot.items():
            if info["runtime_status"] == "connected":
                connected_servers += 1
            elif info["runtime_status"] == "error":
                errors.append(
                    {
                        "server_id": server_id,
                        "message": info["last_error"] or "Unknown MCP error",
                    }
                )

        return {
            "ok": True,
            "connected_servers": connected_servers,
            "failed_servers": len(errors),
            "errors": errors,
        }
