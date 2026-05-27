import os
from pathlib import Path
from typing import Optional
from agent_prototype.api.dto.schemas import SkillSummary

def build_skill_catalog_prompt(skills: list[SkillSummary]) -> str:  # 把 skill 摘要列表拼成给模型看的目录文本
    """输入：SkillSummary 列表。输出：只包含启用 skill 摘要的目录文本。"""
    enabled_skills = [skill for skill in skills if skill.enabled]  # 只把启用中的 skill 放进 catalog

    if not enabled_skills:  # 如果当前没有任何可用 skill
        return "Available skills:\n- none"  # 返回一个最小占位目录

    lines = ["Available skills:"]  # 先放目录标题，告诉模型下面是可选 skill 清单

    for skill in enabled_skills:  # 逐个把启用中的 skill 摘要加到目录里
        description = skill.description or "No description"  # description 为空时给一个兜底文案
        lines.append(f"- {skill.name}: {description}")  # 每行只放名字和摘要，不放完整 instructions

    return "\n".join(lines)  # 用换行把多行目录拼成最终 prompt 文本

def build_runtime_system_prompt(
    base_system_prompt: str,
    skill_catalog_prompt: str,
    selected_skill_content: Optional[str] = None,
    session_type: str = "coding",
    workspace_path: Optional[str] = None,
) -> str:
    """双轨制 System Prompt 拼接拼装核心逻辑。
    
    输入：
    - base_system_prompt: 基础定义人设提示词
    - skill_catalog_prompt: 已加载 skill 目录文本
    - selected_skill_content: 选定的具体激活 skill 提示词
    - session_type: 会话类型 ("coding" | "assistant")
    - workspace_path: 绑定的工作区物理路径
    
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
        if base_system_prompt and "you are a software engineer" not in base_system_prompt.lower():
            sections.append(base_system_prompt)
    # ── 2. 加载技能与 Skill 目录 ──
    sections.append(skill_catalog_prompt)
    if selected_skill_content:
        sections.append(f"Selected skill instructions:\n{selected_skill_content}")
    # ── 3. 工作区本地心智规约与 AGENTS.md 规则注入 (Rulebook & Mental Files Injection) ──
    if workspace_path and os.path.exists(workspace_path):
        root = Path(workspace_path).resolve()
        # A. 加载 AGENTS.md（在两种会话类型中都必须作为最高规约注入）
        agents_path = root / "AGENTS.md"
        if agents_path.exists():
            try:
                content = agents_path.read_text(encoding="utf-8").strip()
                if content:
                    # 使用极其瞩目的特定 XML 标记包裹，确保 LLM 深刻识别它的最高优先级
                    sections.append(
                        f"<WORKSPACE_RULES>\n"
                        f"You MUST strictly adhere to the following local rules and architecture standards found in the workspace's AGENTS.md:\n\n"
                        f"{content}\n"
                        f"These local rules take absolute precedence over any default behaviors or coding patterns.\n"
                        f"</WORKSPACE_RULES>"
                    )
            except Exception as e:
                # 容错：防止因文件编码或占用导致执行崩溃
                pass
        # B. 助理会话特有：加载 SOUL.md 人设文件 与 USER.md 用户偏好
        if session_type == "assistant":
            # 灵魂人设注入
            soul_path = root / "SOUL.md"
            if soul_path.exists():
                try:
                    content = soul_path.read_text(encoding="utf-8").strip()
                    if content:
                        sections.append(f"<AGENT_SOUL>\n{content}\n</AGENT_SOUL>")
                except Exception:
                    pass
            # 用户画像/偏好注入
            user_path = root / "USER.md"
            if user_path.exists():
                try:
                    content = user_path.read_text(encoding="utf-8").strip()
                    if content:
                        sections.append(f"<USER_PROFILE>\n{content}\n</USER_PROFILE>")
                except Exception:
                    pass
    return "\n\n".join(sections)