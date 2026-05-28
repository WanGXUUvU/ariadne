"""Workspace 子域。

统一导出工作区层核心类型与服务，使得调用方可以：
    from agent_prototype.memory.workspace import SqliteWorkspaceStore, WorkspaceService
"""

from agent_prototype.memory.workspace.store import SqliteWorkspaceStore
from agent_prototype.memory.workspace.service import WorkspaceService

__all__ = [
    "SqliteWorkspaceStore",
    "WorkspaceService",
]
