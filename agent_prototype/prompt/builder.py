"""
[九层模型 - L2 提示词层 (Prompt Layer)]

文件职责：
- 专注于内存中的、纯粹无状态的提示词模板拼接与字符串合成。
- 拒绝任何物理磁盘 I/O 操作及网络请求，确保 100% 函数级幂等性。
- 实现双轨制人设切换、技能目录清单构建及 XML 标签包裹拼接。

上游依赖：L6 上下文装配层。
下游依赖：无，纯无状态计算函数。
"""

from typing import Optional


def build_skill_catalog_prompt(
    skills: list,
) -> str:  # 把 skill 摘要列表拼成给模型看的目录文本
    """输入：SkillSummary 列表。输出：只包含启用 skill 摘要的目录文本。"""
    enabled_skills = [
        skill for skill in skills if skill.enabled
    ]  # 只把启用中的 skill 放进 catalog

    if not enabled_skills:  # 如果当前没有任何可用 skill
        return "Available skills:\n- none"  # 返回一个最小占位目录

    lines = ["Available skills:"]  # 先放目录标题，告诉模型下面是可选 skill 清单

    for skill in enabled_skills:  # 逐个把启用中的 skill 摘要加到目录里
        description = (
            skill.description or "No description"
        )  # description 为空时给一个兜底文案
        lines.append(
            f"- {skill.name}: {description}"
        )  # 每行只放名字 and 摘要，不放完整 instructions

    return "\n".join(lines)  # 用换行把多行目录拼成最终 prompt 文本


def build_runtime_system_prompt(
    base_system_prompt: str,
    skill_catalog_prompt: str,
    selected_skill_content: Optional[str] = None,
    session_type: str = "coding",
    local_rules_text: Optional[str] = None,
    agent_soul_text: Optional[str] = None,
    user_profile_text: Optional[str] = None,
) -> str:
    """双轨制 System Prompt 拼接拼装核心逻辑 (纯内存无状态函数)。

    输入：
    - base_system_prompt: 基础定义人设提示词
    - skill_catalog_prompt: 已加载 skill 目录文本
    - selected_skill_content: 选定的具体激活 skill 提示词
    - session_type: 会话类型 ("coding" | "assistant")
    - local_rules_text: 外部读取的本地规约文本 (如原 AGENTS.md 内容)
    - agent_soul_text: 外部读取的助理灵魂文件 (如原 SOUL.md 内容)
    - user_profile_text: 外部读取的用户偏好文件 (如原 USER.md 内容)

    输出：
    - 组合拼接后的最终系统运行提示词
    """
    sections = []
    # ── 1. 双轨提示词分级装配 (Steering Prompt Separation) ──
    if session_type == "coding":
        # 编码产品：使用底座内置专业的高工提示词
        sections.append(base_system_prompt)
    else:
        # 助理产品：底座执行白板模式 (Tabula Rasa)！
        # 仅加载自定义定义中的提示词（非内置 Agent 创建的人设内容），如果是内置 default/engineer 则彻底略去，绝不产生人设冲突
        # 我们假设非 builtin 定义或用户在 AgentManager 中自定义了 system_prompt 时，才追加进去
        if (
            base_system_prompt
            and "you are a software engineer" not in base_system_prompt.lower()
        ):
            sections.append(base_system_prompt)
    # ── 2. 加载技能与 Skill 目录 ──
    sections.append(skill_catalog_prompt)
    if selected_skill_content:
        sections.append(f"Selected skill instructions:\n{selected_skill_content}")
    # ── 3. 工作区本地心智规约与 AGENTS.md 规则注入 (Rulebook & Mental Files Injection) ──
    if local_rules_text:
        # 使用极其瞩目的特定 XML 标记包裹，确保 LLM 深刻识别它的最高优先级
        sections.append(
            f"<WORKSPACE_RULES>\n"
            f"You MUST strictly adhere to the following local rules and architecture standards found in the workspace's AGENTS.md:\n\n"
            f"{local_rules_text}\n"
            f"These local rules take absolute precedence over any default behaviors or coding patterns.\n"
            f"</WORKSPACE_RULES>"
        )
    # B. 助理会话特有：加载 SOUL.md 人设文件 与 USER.md 用户偏好
    if session_type == "assistant":
        # 灵魂人设注入
        if agent_soul_text:
            sections.append(f"<AGENT_SOUL>\n{agent_soul_text}\n</AGENT_SOUL>")
        # 用户画像/偏好注入
        if user_profile_text:
            sections.append(f"<USER_PROFILE>\n{user_profile_text}\n</USER_PROFILE>")

    return "\n\n".join(sections)
