from ..core.schemas import SkillSummary
from ..skills.skill_loader import list_skills,save_skill_config,load_skill_config,DEFAULT_PROTECTED_SKILL_NAMES
def disable_skill_service(skill_name:str)->SkillSummary:
    """输入：要禁用的 skill 名称。输出：禁用后的 SkillSummary。"""
    skills = list_skills()
    target = next((skill for skill in skills if skill.name==skill_name),None)

    if target is None:
        raise ValueError(f"Skill not found:{skill_name}")
    
    if skill_name in DEFAULT_PROTECTED_SKILL_NAMES:
        raise ValueError(f"Skill is protected and cannot be disabled: {skill_name}")
    
    config = load_skill_config()
    config.disabled.add(skill_name) #把目标skill加入禁用合集
    save_skill_config(config)

    updated_skills = list_skills()
    updated_target = next(skill for skill in updated_skills if skill.name == skill_name)  # 取回更新后的目标 skill

    return updated_target  # 返回更新后的 skill 摘要，给 route 或调用方继续使用

def enable_skill_service(skill_name:str)->SkillSummary:
    """输入：要启用的 skill 名称。输出：启用后的 SkillSummary。"""
    skills = list_skills()
    target = next((skill for skill in skills if skill.name==skill_name),None)

    if target is None:
        raise ValueError(f"Skill not found:{skill_name}")
    
    config = load_skill_config()
    config.disabled.discard(skill_name)#discard() 如果名字本来就不在集合里，不报错
    save_skill_config(config)

    updated_skills=list_skills()
    updated_target = next(skill for skill in updated_skills if skill.name == skill_name)  # 取回更新后的目标 skill

    return updated_target  # 返回更新后的 skill 摘要，给 route 或调用方继续使用
