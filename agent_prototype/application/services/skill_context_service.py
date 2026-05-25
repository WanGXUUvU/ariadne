from sqlalchemy.orm import Session

from agent_prototype.core.agent_definition import AgentDefinition
from agent_prototype.interface.dto.schemas import AgentInput, SkillSummary
from agent_prototype.application.runtime.context.prompt_builder import (
    build_runtime_system_prompt,
    build_skill_catalog_prompt
)
from agent_prototype.infrastructure.skills.skill_loader import (
    list_skills as loader_list_skills,
    load_skill_content as loader_load_skill_content
)


class SkillContextService:
    """运行上下文注入服务类 (OOP)
    
    职责：
    1. 负责拼装合并模型所能看到的内置技能清单的描述词 (Catalog)；
    2. 如果当前请求指定了具体技能，加载其正文注入 Agent 执行系统提示词。
    """
    
    def __init__(self, db: Session = None):
        """构造注入"""
        self.db = db

    def _get_selected_skill_or_raise(self, skill_name: str, skills: list[SkillSummary]) -> SkillSummary:
        """内部方法：校验技能是否已就绪且处于激活状态"""
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
        agent_input: AgentInput,
    ) -> AgentDefinition:
        """将选定的技能目录及内容组合进 Agent 的系统提示词中，返回更新后的定义实体"""
        skills = loader_list_skills()
        skill_catalog_prompt = build_skill_catalog_prompt(skills)
        selected_skill_content = None

        if agent_input.skill_name:
            self._get_selected_skill_or_raise(agent_input.skill_name, skills)
            selected_skill_content = loader_load_skill_content(agent_input.skill_name)

        runtime_system_prompt = build_runtime_system_prompt(
            definition.system_prompt,
            skill_catalog_prompt,
            selected_skill_content,
        )

        return definition.model_copy(
            update={"system_prompt": runtime_system_prompt}
        )

