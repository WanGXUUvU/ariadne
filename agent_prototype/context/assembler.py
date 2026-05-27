"""
[九层模型 - L6 上下文装配层 (Context Assembly Layer)]

文件职责：
- 作为系统首个集中式的物理文件读取与规约注入总调度器（ContextAssembler）。
- 集中处理工作区磁盘文件（AGENTS.md, SOUL.md, USER.md）的物理读取和容错保护。
- 调用 SkillContextService 组装技能描述并交付 L2 纯内存提示词合成。

上游依赖：L8 执行层 (RunContextBuilder)。
下游依赖：L6 技能上下文服务 (SkillContextService)、L2 提示词层 (builder.py)。
"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from sqlalchemy.orm import Session

from agent_prototype.agent.definition import AgentDefinition
from agent_prototype.api.dto.schemas import AgentInput
from agent_prototype.context.skill_context import SkillContextService


@dataclass
class AssembledContext:
    """拼装后的上下文对象。"""
    system_prompt: str
    workspace_path: Optional[str]


class ContextAssembler:
    """统一的运行上下文装配服务 (L6 层)。
    
    职责：
    1. 集中处理物理磁盘文件的读取（AGENTS.md, SOUL.md, USER.md）；
    2. 调用 SkillContextService 装配技能与提示词；
    3. 返回统一的 AssembledContext，供执行层 RunContextBuilder 消费。
    """

    def __init__(self, db: Session):
        self.db = db
        self.skill_service = SkillContextService(db)

    def assemble(
        self,
        agent_input: AgentInput,
        session_type: str,
        workspace_path: Optional[str],
        definition: AgentDefinition,
    ) -> AssembledContext:
        """物理磁盘文件读取 + 技能目录拼装的统一入口"""
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
                    pass

            # B. 助理会话特有：加载 SOUL.md 与 USER.md
            if session_type == "assistant":
                soul_path = root / "SOUL.md"
                if soul_path.exists():
                    try:
                        content = soul_path.read_text(encoding="utf-8").strip()
                        if content:
                            agent_soul_text = content
                    except Exception:
                        pass

                user_path = root / "USER.md"
                if user_path.exists():
                    try:
                        content = user_path.read_text(encoding="utf-8").strip()
                        if content:
                            user_profile_text = content
                    except Exception:
                        pass

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
