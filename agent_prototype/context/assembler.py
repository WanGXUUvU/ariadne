"""
[九层模型 - L6 上下文装配层 (Context Assembly Layer)]

文件职责：
- 作为系统首个集中式的物理文件读取与规约注入总调度器（ContextAssembler）。
- 集中处理工作区磁盘文件（AGENTS.md, SOUL.md, USER.md）的物理读取和容错保护。
- 调用 SkillContextService 组装技能描述并交付 L2 纯内存提示词合成。

上游依赖：L8 执行层 (RunContextBuilder)。
下游依赖：L6 技能上下文服务 (SkillContextService)、L2 提示词层 (builder.py)。
"""
import logging
import os
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session

from agent_prototype.core.types import AgentDefinition
from agent_prototype.core.types import AgentInput
from agent_prototype.context.skill_context import SkillContextService


from agent_prototype.context.types import AssembledContext


class ContextAssembler:
    """这是一个"大掌柜"角色，专门负责把智能体运行需要的所有背景资料（也就是上下文）给拼装齐全。
    它的主要工作是：去硬盘里读取一些写好的规则文件（比如 AGENTS.md, SOUL.md, USER.md），
    然后结合智能体本身的技能设定，把这些杂七杂八的信息揉成一段完整的系统提示词，装进一个小篮子里吐出来。
    """

    def __init__(self, db: Session):
        """初始化这个大掌柜，给他指派好数据库连接，方便他去找技能数据。

        需要拿到的东西：
        - db: 数据库会话对象，用来连数据库查东西。
        """
        self.db = db
        self.skill_service = SkillContextService(db)

    def assemble(
        self,
        agent_input: AgentInput,
        session_type: str,
        workspace_path: Optional[str],
        definition: AgentDefinition,
    ) -> AssembledContext:
        """开始热火朝天地拼装上下文！它会跑到工作区路径下去读那些本地规则文件，
        如果是助理模式还会去读灵魂和用户信息，再配合上技能，打包弄出一个完美的系统提示词。

        需要拿到的东西：
        - agent_input: 用户传过来的输入参数（比如希望带上的临时提示词等）。
        - session_type: 会话类型（是助理模式 'assistant' 还是其他模式）。
        - workspace_path: 工作区在电脑里的具体文件夹路径。如果传了，大掌柜就会进去翻文件。
        - definition: 智能体本尊的定义信息（包含它自带的一些基础提示词设定）。

        会给出来的结果：
        - 一个 AssembledContext 对象，里面包含了最终揉好的 system_prompt（系统提示词）和工作区路径。
        """
        local_rules_text = None
        agent_soul_text = None
        user_profile_text = None

        if workspace_path and os.path.exists(workspace_path):
            root = Path(workspace_path).resolve()
            
            # A. 加载 AGENTS.md（在两种会话类型中都作为最高规约注入）
            agents_path = root / "AGENTS.md"
            if agents_path.exists():
                try:
                    content = agents_path.read_text(encoding="utf-8").strip()
                    if content:
                        local_rules_text = content
                except Exception:
                    logging.getLogger(__name__).warning(
                        "Failed to read AGENTS.md from %s", agents_path, exc_info=True
                    )

            # B. 助理会话特有：加载 SOUL.md 与 USER.md
            if session_type == "assistant":
                soul_path = root / "SOUL.md"
                if soul_path.exists():
                    try:
                        content = soul_path.read_text(encoding="utf-8").strip()
                        if content:
                            agent_soul_text = content
                    except Exception:
                        logging.getLogger(__name__).warning(
                            "Failed to read SOUL.md from %s", soul_path, exc_info=True
                        )

                user_path = root / "USER.md"
                if user_path.exists():
                    try:
                        content = user_path.read_text(encoding="utf-8").strip()
                        if content:
                            user_profile_text = content
                    except Exception:
                        logging.getLogger(__name__).warning(
                            "Failed to read USER.md from %s", user_path, exc_info=True
                        )

        # 调用 SkillContextService 完成纯内存的技能和提示词装配
        runtime_definition = self.skill_service.build_runtime_definition_with_skills(
            definition=definition,
            agent_input=agent_input,
            session_type=session_type,
            local_rules_text=local_rules_text,
            agent_soul_text=agent_soul_text,
            user_profile_text=user_profile_text,
        )

        return AssembledContext(
            system_prompt=runtime_definition.system_prompt,
            workspace_path=workspace_path,
        )
