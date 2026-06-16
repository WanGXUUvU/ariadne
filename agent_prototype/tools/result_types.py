"""工具调用结果类型定义。

职责：
- 定义工具运行终态的结构化结果：ToolResult 与 ToolError。
- 作为运行时、安全层及业务编排层的统一通信契约。

上游：
- ToolRegistry
- 各内置工具的执行 handler

下游：
- Runner / execution 运行时
- Observation / trace 审计层

不负责：
- 不做工具静态注册声明（见 tools/types.py）。
- 不做具体模型协议消息转换（见 core/types.py）。
"""

from typing import Any, Optional
from enum import Enum

from pydantic import BaseModel, Field


class ToolError(BaseModel):
    """工具失败时返回给上层的结构化错误。"""

    ok: bool = False
    code: str
    tool_name: str
    message: str


class ToolResult(BaseModel):
    """统一的工具执行结果。"""

    ok: bool
    content: Optional[str] = None
    error: Optional[ToolError] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolState(str, Enum):
    """工具写入的vfs状态。"""

    STAGED = "staged"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
