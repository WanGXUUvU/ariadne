"""技能上下文服务。

职责：
- 列出当前可用技能并生成技能目录提示词。
- 按需加载指定技能的正文内容。
- 将技能上下文拼接进运行期系统提示词。

上游：
- ContextAssembler

下游：
- skills.loader
- prompt.builder

不负责：
- 不读取工作区物理文件。
- 不驱动模型执行。
"""

import sys
from typing import Optional, Callable

from agent_prototype.agent.types import AgentDefinition
from agent_prototype.execution.persistence.types import RunInput
from agent_prototype.skills.loader import (
    list_skills as default_list_skills,
    load_skill_content as default_load_skill_content,
)

list_skills = default_list_skills
load_skill_content = default_load_skill_content


class SkillContextService:
    """负责生成运行期技能上下文。"""

    def __init__(
        self,
        list_skills: Optional[Callable] = None,
        load_skill_content: Optional[Callable[[str], Optional[str]]] = None,
        build_skill_catalog_prompt: Optional[Callable] = None,
        build_runtime_system_prompt: Optional[Callable] = None,
    ):
        """通过依赖注入接收技能和 prompt 构建回调。"""
        module = sys.modules[__name__]
        self._list_skills = list_skills or getattr(
            module, "list_skills", default_list_skills
        )
        self._load_skill_content = load_skill_content or getattr(
            module,
            "load_skill_content",
            default_load_skill_content,
        )
        self._build_skill_catalog_prompt = build_skill_catalog_prompt
        self._build_runtime_system_prompt = build_runtime_system_prompt

    def _get_selected_skill_or_raise(self, skill_name: str, skills: list) -> object:
        """返回已启用的目标技能；找不到或禁用则抛错。"""
        selected_skill = next(
            (skill for skill in skills if skill.name == skill_name),
            None,
        )

        if selected_skill is None:
            raise ValueError(f"Skill not found: {skill_name}")

        if not selected_skill.enabled:
            raise ValueError(f"Skill is disabled: {skill_name}")

        return selected_skill

    def build_runtime_definition_with_skills(
        self,
        definition: AgentDefinition,
        run_input: RunInput,
        session_type: str = "coding",
        local_rules_text: Optional[str] = None,
        agent_soul_text: Optional[str] = None,
        user_profile_text: Optional[str] = None,
    ) -> AgentDefinition:
        """返回注入技能上下文后的运行期 AgentDefinition。"""
        skills = self._list_skills()
        skill_catalog_prompt = self._build_skill_catalog_prompt(skills)
        selected_skill_content = None

        if run_input.skill_name:
            self._get_selected_skill_or_raise(run_input.skill_name, skills)
            selected_skill_content = self._load_skill_content(run_input.skill_name)

        runtime_system_prompt = self._build_runtime_system_prompt(
            definition.system_prompt,
            skill_catalog_prompt,
            selected_skill_content,
            session_type=session_type,
            local_rules_text=local_rules_text,
            agent_soul_text=agent_soul_text,
            user_profile_text=user_profile_text,
        )

        return definition.model_copy(update={"system_prompt": runtime_system_prompt})
