from ..core.schemas import SkillSummary  # 导入 skill 摘要模型

from typing import Optional

def build_skill_catalog_prompt(skills: list[SkillSummary]) -> str:  # 把 skill 摘要列表拼成给模型看的目录文本
    enabled_skills = [skill for skill in skills if skill.enabled]  # 只把启用中的 skill 放进 catalog

    if not enabled_skills:  # 如果当前没有任何可用 skill
        return "Available skills:\n- none"  # 返回一个最小占位目录

    lines = ["Available skills:"]  # 先放目录标题，告诉模型下面是可选 skill 清单

    for skill in enabled_skills:  # 逐个把启用中的 skill 摘要加到目录里
        description = skill.description or "No description"  # description 为空时给一个兜底文案
        lines.append(f"- {skill.name}: {description}")  # 每行只放名字和摘要，不放完整 instructions

    return "\n".join(lines)  # 用换行把多行目录拼成最终 prompt 文本

def build_runtime_system_prompt(
        base_system_prompt:str,
        skill_catalog_prompt:str,
        selected_skill_content:Optional[str]=None,
)->str:
    
    sections=[base_system_prompt,skill_catalog_prompt]

    if selected_skill_content:
        sections.append(f"Selected skill instructions:\n{selected_skill_content}")

    return "\n\n".join(sections)  # 用空行把各段拼起来，提升可读性
