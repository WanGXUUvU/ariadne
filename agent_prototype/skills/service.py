"""应用服务层 (Application Layer) - 动态技能编排

职责：
1. 编排系统动态技能加载、卸载、启用、禁用的全部业务逻辑。
2. 动态扫描和管理技能在运行时上下文中的参数映射。

不负责：
1. 技能 Python 插件模块的底层物理动态导入细节（由 Loader 负责）。
2. 技能的物理文件增删。

数据流向：
- 输入：技能唯一标识及启用参数。
- 输出：启用的技能元数据及组装工具。
- 上游来源：agent_prototype/api/routes/skill_routes.py。
- 下游流向：调用 agent_prototype/skills/loader.py。
"""

from agent_prototype.skills.types import SkillSummary
from agent_prototype.skills.loader import (
    list_skills as loader_list_skills,
    save_skill_config,
    load_skill_config,
    DEFAULT_PROTECTED_SKILL_NAMES,
)


class SkillService:
    """技能管理服务类 (OOP)

    职责：
    1. 负责本地方案支持技能的发现、状态清单的导出；
    2. 提供细粒度的技能状态（激活/停用）管理。
    """

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
