from sqlalchemy.orm import Session

from agent_prototype.api.dto.schemas import SkillSummary
from agent_prototype.skills.loader import (
    list_skills as loader_list_skills,
    save_skill_config,
    load_skill_config,
    DEFAULT_PROTECTED_SKILL_NAMES
)


class SkillService:
    """技能管理服务类 (OOP)
    
    职责：
    1. 负责本地方案支持技能的发现、状态清单的导出；
    2. 提供细粒度的技能状态（激活/停用）管理。
    """
    
    def __init__(self, db: Session = None):
        """构造函数依赖注入：聚合 db 会话，支持规范结构"""
        self.db = db

    def list_skills(self) -> list[SkillSummary]:
        """获取所有可用技能清单"""
        return loader_list_skills()

    def _get_skill_or_raise(self, skill_name: str) -> SkillSummary:
        """内部方法：校验技能是否存在，不存在则抛 ValueError 异常"""
        skills = self.list_skills()
        target = next((skill for skill in skills if skill.name == skill_name), None)

        if target is None:
            raise ValueError(f"Skill not found: {skill_name}")
        return target

    def _reload_skill(self, skill_name: str) -> SkillSummary:
        """内部方法：重新加载更新后的技能实体状态"""
        updated_skills = self.list_skills()
        return next(skill for skill in updated_skills if skill.name == skill_name)

    def disable_skill(self, skill_name: str) -> SkillSummary:
        """停用指定的技能"""
        self._get_skill_or_raise(skill_name)

        if skill_name in DEFAULT_PROTECTED_SKILL_NAMES:
            raise ValueError(f"Skill is protected and cannot be disabled: {skill_name}")
        
        config = load_skill_config()
        config.disabled.add(skill_name)
        save_skill_config(config)

        return self._reload_skill(skill_name)

    def enable_skill(self, skill_name: str) -> SkillSummary:
        """激活启用的技能"""
        self._get_skill_or_raise(skill_name)
        
        config = load_skill_config()
        config.disabled.discard(skill_name)
        save_skill_config(config)

        return self._reload_skill(skill_name)

