"""
[九层模型 - L6 上下文装配层 (Context Assembly Layer)]

文件职责：
- 充当技能上下文与人设缝合器（SkillContextService）。
- 负责扫描内置 Skills，将可用技能的说明文字进行 Catalog 目录清单整合。
- 根据用户会话请求，动态提取指定激活技能的内容并喂入 Prompt 合成链路。

上游依赖：L6 上下文装配器 (assembler.py)。
下游依赖：L4 技能载入层 (loader.py)、L2 提示词层 (builder.py)。
"""
from sqlalchemy.orm import Session
from typing import Optional

from agent_prototype.agent.definition import AgentDefinition
from agent_prototype.api.dto.schemas import AgentInput, SkillSummary
from agent_prototype.prompt.builder import (
    build_runtime_system_prompt,
    build_skill_catalog_prompt
)
from agent_prototype.skills.loader import (
    list_skills as loader_list_skills,
    load_skill_content as loader_load_skill_content
)


class SkillContextService:
    """这是一个“技能与人设缝合器”服务。
    它的主要功能是帮我们管理和拼装各种“技能描述”与“性格人设（灵魂）”。
    它会去扫描系统自带了哪些技能，把这些技能做成一个“技能清单”，让大模型知道它都能干嘛。
    如果用户指定要用某个特定技能，它还会去把那个技能的具体操作指引内容读取出来，塞进大模型的系统提示词里。
    """
    
    def __init__(self, db: Session = None):
        """初始化缝合器服务，指定数据库连接。

        需要拿到的东西：
        - db: 数据库连接会话对象（非必传，留着备用）。
        """
        self.db = db

    def _get_selected_skill_or_raise(self, skill_name: str, skills: list[SkillSummary]) -> SkillSummary:
        """内部使用的一个“严格质检员”小帮手。
        它用来检查用户想要的某个技能存不存在，并且看看这个技能是不是正开着（激活状态）。
        如果找不到或者没开，它就会生气地抛出异常（ValueError）不干了。

        需要拿到的东西：
        - skill_name: 用户想要使用的技能名字。
        - skills: 当前系统里所有可用技能的总结清单列表。

        会给出来的结果：
        - 如果检查合格，就返回那个被选中的 SkillSummary 技能信息对象。
        """
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
        session_type: str = "coding",
        local_rules_text: Optional[str] = None,
        agent_soul_text: Optional[str] = None,
        user_profile_text: Optional[str] = None,
    ) -> AgentDefinition:
        """这是缝合器的核心大招！它把智能体原有的基本设定、当前能用的所有技能清单、
        用户这次点名要用的特定技能指引、还有从硬盘里读出来的本地规则/灵魂/用户信息，
        全部完美缝合在一起，生成一段超级无敌详细的、给大模型看的系统提示词，
        最后返回一个换上了这套新系统提示词的智能体新定义实体。

        需要拿到的东西：
        - definition: 智能体原有的基础定义配置。
        - agent_input: 包含了这次运行输入参数的对象（比如用户指名要用的技能）。
        - session_type: 会话类型，比如是写代码模式 "coding" 还是助理模式 "assistant"。
        - local_rules_text: 从本地读出来的规约规则文本（比如 AGENTS.md 的内容）。
        - agent_soul_text: 智能体灵魂设定文本（比如 SOUL.md 的内容）。
        - user_profile_text: 用户画像文本（比如 USER.md 的内容）。

        会给出来的结果：
        - 一个全新的 AgentDefinition 智能体定义实体，它里面的 `system_prompt` 已经完美混入了以上所有信息。
        """
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
            session_type=session_type,
            local_rules_text=local_rules_text,
            agent_soul_text=agent_soul_text,
            user_profile_text=user_profile_text,
        )

        return definition.model_copy(
            update={"system_prompt": runtime_system_prompt}
        )
