"""工具调用结果类型。

职责：
- 定义工具执行阶段的结构化结果与错误模型。
- 供 tools/security/execution/observation 等运行时模块共享。

不负责：
- 不定义工具注册声明（见 tools/types.py）。
- 不定义模型协议消息（见 core/types.py）。
"""

from typing import Any, Optional

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
