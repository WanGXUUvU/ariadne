"""
[九层模型 - 智能体定义层 (Agent Definition Layer)]

文件职责：
- 定义智能体（Agent）的人设、系统提示词、允许挂载工具清单等核心静态属性（AgentDefinition）。
- 提供系统默认智能体及默认助理智能体实例的硬编码退化兜底。

上游依赖：L8 执行层 (RunService)、L6 上下文层 (ContextAssembler)、L10 API 接口层 DTO。
下游依赖：无。
"""
from typing import Optional

from pydantic import BaseModel, Field


# ── 领域模型 ──────────────────────────────────────────────────────────────────

class AgentDefinition(BaseModel):
    """这个类是用来描述一个智能体（Agent）的“人设和超能力”配置定义的。
    
    每个 Agent 都需要有自己独特的性格和擅长的事情。比如，这个 Agent 叫什么名字、它说话的语气是怎样的（系统提示词）、它身上带了哪些工具，都由这个类来统一装载和记录。
    
    这个类包含的属性有：
    - id: 字符串，这个 Agent 的唯一身份证 ID（例如 'assistant'）。
    - name: 字符串，它的名字（比如 '翻译助手'）。
    - system_prompt: 字符串，给它的角色扮演人设和系统提示词（比如 '你是一个高级翻译员，请翻译以下文本'）。
    - description: 可选的字符串，大白话描述这个 Agent 是干嘛的，方便人看懂。
    - tool_names: 可选的字符串列表，用来声明这个 Agent 能够使用哪些工具的名字列表（为 None 表示它可以使用所有工具）。
    - is_builtin: 布尔值，代表这个 Agent 是不是系统里原本自带的（内置的通常不能被删掉）。
    """

    id: str = Field(default="default")
    name: str = Field(default="Default Agent")
    system_prompt: str = Field(default="你是一个助手")
    description: Optional[str] = None
    tool_names: Optional[list[str]] = None  # None 表示不限制，暴露全部工具
    is_builtin: bool = False                # True 表示来自内置 .md 文件，不可删除


# ── 内置预设定义 ──────────────────────────────────────────────────────────────

DEFAULT_AGENT_DEFINITION = AgentDefinition()

ASSISTANT_AGENT_DEFINITION = AgentDefinition(
    id="assistant",
    name="Chat Assistant",
    system_prompt=(
        "你是一个友好、简洁、诚实的通用助理。"
        "回答时直接切入要点，不确定的事情如实说明，不要编造信息。"
    ),
    description="帮助用户完成日常任务",
    tool_names=["web_search"],
)
