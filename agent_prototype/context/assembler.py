"""工作区上下文装配器。

职责：
- 读取工作区中的 AGENTS.md / SOUL.md / USER.md。
- 将本地规则、用户画像和技能上下文交给 SkillContextService。
- 产出一次运行所需的系统提示词和工作区元信息。

上游：
- RunContextFactory

下游：
- SkillContextService

不负责：
- 不直接驱动模型。
- 不感知数据库持久化。
"""

import agent_prototype.context.skill_context as skill_context_module
import logging
import os
from pathlib import Path
from typing import Callable, Optional

from sqlalchemy.orm import Session

from agent_prototype.agent.types import AgentDefinition
from agent_prototype.context.types import AssembledContext
from agent_prototype.context.skill_context import SkillContextService
from agent_prototype.execution.persistence.types import AgentInput


class ContextAssembler:
    """负责拼装运行期工作区上下文。"""

    def __init__(
        self,
        db: Session,
        list_skills: Optional[Callable] = None,
        load_skill_content: Optional[Callable[[str], Optional[str]]] = None,
        build_skill_catalog_prompt: Optional[Callable] = None,
        build_runtime_system_prompt: Optional[Callable] = None,
    ):
        """使用技能加载器和 prompt 构建器装配 SkillContextService。"""
        self.db = db
        self.skill_service = SkillContextService(
            list_skills=list_skills or skill_context_module.list_skills,
            load_skill_content=load_skill_content or skill_context_module.load_skill_content,
            build_skill_catalog_prompt=build_skill_catalog_prompt,
            build_runtime_system_prompt=build_runtime_system_prompt,
        )

    def assemble(
        self,
        agent_input: AgentInput,
        session_type: str,
        workspace_path: Optional[str],
        definition: AgentDefinition,
    ) -> AssembledContext:
        """读取工作区文本上下文并产出运行期系统提示词。"""
        local_rules_text, agent_soul_text, user_profile_text = self._load_workspace_context(
            workspace_path,
            session_type,
        )

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

    def _load_workspace_context(
        self,
        workspace_path: Optional[str],
        session_type: str,
    ) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """读取工作区规则、灵魂和用户画像文本。"""
        if not workspace_path or not os.path.exists(workspace_path):
            return None, None, None

        root = Path(workspace_path).resolve()
        local_rules_text = self._read_optional_text(root / "AGENTS.md")
        agent_soul_text = None
        user_profile_text = None

        if session_type == "assistant":
            agent_soul_text = self._read_optional_text(root / "SOUL.md")
            user_profile_text = self._read_optional_text(root / "USER.md")

        return local_rules_text, agent_soul_text, user_profile_text

    def _read_optional_text(self, path: Path) -> Optional[str]:
        """读取一个可选文本文件；不存在或为空时返回 None。"""
        if not path.exists():
            return None
        try:
            content = path.read_text(encoding="utf-8").strip()
        except Exception:
            logging.getLogger(__name__).warning("Failed to read %s", path, exc_info=True)
            return None
        return content or None
