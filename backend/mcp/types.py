from dataclasses import dataclass, field
from enum import Enum


class McpTranSport(str, Enum):
    STDIO = "stdio"
    STREAMABLE_HTTP = "streamable_http"


@dataclass(frozen=True)
class McpServerConfig:
    sever_id: str
    display_name: str | None
    transport: McpTranSport
    enable: bool = True
    required: bool = False
    startup_timeout_sec: int = 10
    tool_timeout_sec: int = 30


@dataclass(frozen=True)
class StdioMcpServerConfig(McpServerConfig):
    command: str = ""
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None


@dataclass(frozen=True)
class StreamableHttpMcpServerConfig(McpServerConfig):
    url: str = ""
    bearer_token: str | None = None
    http_headers: dict[str, str] = field(default_factory=dict)
