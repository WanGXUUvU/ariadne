"""智能体模块。

统一导出智能体核心类型与服务，使得调用方可以：
    from agent_prototype.agent import AgentDefinition, AgentDefinitionService
"""

from agent_prototype.agent.types import AgentDefinition, DEFAULT_AGENT_DEFINITION, ASSISTANT_AGENT_DEFINITION
from agent_prototype.agent.definition import AgentDefinitionService, SqliteAgentDefinitionStore, list_builtin_agents
from agent_prototype.agent.settings import SettingsService, SqliteSettingsStore

__all__ = [
    # types
    "AgentDefinition",
    "DEFAULT_AGENT_DEFINITION",
    "ASSISTANT_AGENT_DEFINITION",
    # definition
    "AgentDefinitionService",
    "SqliteAgentDefinitionStore",
    "list_builtin_agents",
    # settings
    "SettingsService",
    "SqliteSettingsStore",
]
