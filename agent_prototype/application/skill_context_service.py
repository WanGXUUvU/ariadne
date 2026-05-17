from ..core.agent_definition import AgentDefinition
from ..core.schemas import AgentInput, SkillSummary
from ..context.prompt_builder import build_runtime_system_prompt, build_skill_catalog_prompt
from ..skills.skill_loader import list_skills, load_skill_content


def _get_selected_skill_or_raise(skill_name: str, skills: list[SkillSummary]) -> SkillSummary:
    """输入：skill 名称、skill 摘要列表。输出：校验通过的 SkillSummary。"""

    selected_skill = next(
        (skill for skill in skills if skill.name == skill_name),
        None,
    )

    if selected_skill is None:
        raise ValueError(f"Skill not found:{skill_name}")

    if not selected_skill.enabled:
        raise ValueError(f"Skill is disabled:{skill_name}")

    return selected_skill

    
def build_runtime_definition_with_skills(
    definition: AgentDefinition,
    agent_input: AgentInput,
    list_skills=list_skills,
    load_skill_content=load_skill_content,
) -> AgentDefinition:
    """输入：agent 定义、AgentInput 请求对象。输出：带 skill 上下文的 runtime definition。"""

    skills = list_skills()  # 先拿到所有本地 skill 的摘要列表
    skill_catalog_prompt = build_skill_catalog_prompt(skills)  # 把摘要列表拼成给模型看的 skill 目录
    selected_skill_content = None  # 默认这轮不加载任何 skill 正文

    if agent_input.skill_name:  # 如果这轮请求显式指定了某个 skill
        _get_selected_skill_or_raise(agent_input.skill_name, skills)
        selected_skill_content = load_skill_content(agent_input.skill_name)

    runtime_system_prompt = build_runtime_system_prompt(
        definition.system_prompt,
        skill_catalog_prompt,
        selected_skill_content,
    )

    return definition.model_copy(
        update={"system_prompt": runtime_system_prompt}
    )