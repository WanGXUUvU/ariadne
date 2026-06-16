"""智能体配置子模块。

统一导出配置层核心类型与服务，使得调用方可以：
    from backend.agent.settings import SettingsService, SqliteSettingsStore
"""

from backend.agent.settings.service import SettingsService
from backend.agent.settings.store import SqliteSettingsStore

__all__ = [
    "SettingsService",
    "SqliteSettingsStore",
]
