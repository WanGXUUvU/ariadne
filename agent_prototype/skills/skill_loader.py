from pathlib import Path
from typing import Optional

from ..core.schemas import SkillSummary
from . import skill_config as _skill_config
from .skill_config import (
    DEFAULT_PROTECTED_SKILL_NAMES,
    SkillConfig,
)


def get_default_skill_config_path() -> Path:
    return _skill_config.get_default_skill_config_path()


def load_skill_config(config_path: Optional[Path] = None) -> SkillConfig:
    path = config_path or get_default_skill_config_path()
    return _skill_config.load_skill_config(path)


def is_skill_disabled(skill_name: str, config: SkillConfig) -> bool:
    return _skill_config.is_skill_disabled(skill_name, config)


def save_skill_config(config: SkillConfig, config_path: Optional[Path] = None) -> None:
    path = config_path or get_default_skill_config_path()
    _skill_config.save_skill_config(config, path)


def get_default_skill_roots() -> list[tuple[str, Path]]:  # 返回默认要扫描的skill的根目录
    """输入：无。输出：默认 skill 根目录列表。"""
    repo_root = Path(__file__).resolve().parents[2]  # 从当前文件反推到仓库根目录
    package_root = Path(__file__).resolve().parents[1]  # 反推到agent_prototype根目录
    home_root = Path.home()  # 全局目录
    return [  # 返回“来源标签 + 实际路径”，方便后面做安全 path
        ("opencode", repo_root / ".opencode" / "skills"),  # 项目内 opencode skills 目录
        ("agents", repo_root / ".agents" / "skills"),  # 项目内 agents skills 目录
        ("builtin", package_root / "skills"),  # 应用内置 skills 目录
        ("user-codex", home_root / ".codex" / "skills"),  # 用户级skill
        ("user", home_root / ".agents" / "skills"),
    ]


def list_skills(
    skill_roots: Optional[list[tuple[str, Path]]] = None,
    config_path: Optional[Path] = None,
) -> list[SkillSummary]:
    """输入：可选的 skill 根目录列表、可选的配置文件路径。输出：合并启用状态后的 SkillSummary 列表。"""
    roots = skill_roots or get_default_skill_roots()  # 没传目录时，使用默认 skill 扫描目录
    if config_path is not None or skill_roots is None:
        config = load_skill_config(config_path)  # 先读取 skill 配置，拿到 disabled 名单
    else:
        config = SkillConfig(disabled=set())  # 测试/自定义 roots 场景默认不叠加全局配置
    results: list[SkillSummary] = []  # 返回的结果

    for source_name, root_path in roots:  # 逐个扫描每个目录
        if not root_path.exists():  # 目录不存在直接提哦啊过
            continue

        for skill_file in sorted(root_path.glob("*/SKILL.md")):  # 只匹配一级目录下的SKILL.md
            summary = _load_skill_summary(skill_file, source_name, root_path)  # 先按原逻辑解析出一个 SkillSummary
            if summary.enabled and is_skill_disabled(summary.name, config):
                summary = summary.model_copy(update={"enabled": False})  # 命中 disabled 名单时，把 enabled 改成 False

            results.append(summary)  # 逐个读取摘要

    return sorted(results, key=lambda item: item.name.lower())


def _load_skill_summary(skill_file: Path, source_name: str, root_path: Path) -> SkillSummary:
    """输入：单个 SKILL.md 路径、来源名、来源根目录。输出：一个 SkillSummary。"""
    safe_relative_path = skill_file.relative_to(root_path).as_posix()  # 先算相对路径 /Users/haoyu/.agent/skills/python_debug/SKILL.md
    safe_path = f"{source_name}/{safe_relative_path}"  # 给前端返回“来源+相对路径” user/python_debug/SKILL.md

    try:
        content = skill_file.read_text(encoding="utf-8")
        metadata = _parse_frontmatter(content)
        name = str(metadata.get("name") or skill_file.parent.name)
        description_value = metadata.get("description")
        description = str(description_value) if description_value is not None else None

        return SkillSummary(name=name, description=description, path=safe_path, enabled=True)

    except Exception as exc:
        return SkillSummary(
            name=skill_file.parent.name,
            description=None,
            path=safe_path,
            enabled=False,
            error=str(exc),
        )


def _parse_frontmatter(content: str) -> dict[str, str]:  # 从SKILL.md提取frontmatter字段
    """输入：SKILL.md 全文字符串。输出：frontmatter 键值字典。"""
    lines = content.splitlines()  # 按行拆

    if len(lines) < 3 or lines[0].strip() != "---":  # 没有frontmatter视为坏的skill
        raise ValueError("Missing frontmatter")

    metadata: dict[str, str] = {}  # 存解析出来的键值对

    for line in lines[1:]:  # 从第二行开始读frontmatter 内容
        if line.strip() == "---":
            return metadata

        if ":" not in line:  # frontmatter 行至少要有 key: value
            raise ValueError(f"Invalid frontmatter line: {line}")

        key, value = line.split(":", 1)  # 只按第一个冒号切，避免值里再有冒号时切坏
        metadata[key.strip()] = value.strip().strip('"').strip("'")  # 去掉前后空格和简单引号

    raise ValueError("Frontmatter not closed")  # 没遇到结束边界，说明 frontmatter 不完整


def load_skill_content(skill_name: str, skill_roots: Optional[list[tuple[str, Path]]] = None) -> str:  # 按名字加载完整 skill 正文
    """输入：skill 名称、可选的 skill 根目录列表。输出：目标 skill 的完整 SKILL.md 文本。"""  # 说明这个函数返回的是全文，不是摘要

    roots = skill_roots or get_default_skill_roots()  # 没传自定义目录时，使用默认扫描根目录

    for _, root_path in roots:  # 逐个扫描每个 skill 根目录
        if not root_path.exists():  # 目录不存在时直接跳过
            continue  # 不把缺失目录当成错误

        for skill_file in sorted(root_path.glob("*/SKILL.md")):  # 逐个检查每个 SKILL.md
            try:  # 单个坏 skill 不应该打断整个查找流程
                content = skill_file.read_text(encoding="utf-8")  # 先读完整文件内容
                metadata = _parse_frontmatter(content)  # 解析 frontmatter，拿到 skill 名字
            except Exception:  # 如果这个 skill 自己坏了
                continue  # 直接跳过它，继续找别的 skill

            current_name = str(metadata.get("name") or skill_file.parent.name)  # 优先用 frontmatter.name，没有就退回目录名

            if current_name == skill_name:  # 找到目标 skill
                return content  # 返回完整 SKILL.md 文本

    raise ValueError(f"Skill not found: {skill_name}")  # 所有目录都没找到时抛错