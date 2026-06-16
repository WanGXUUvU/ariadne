"""
[九层模型 - L4 技能层 - 基础设施 (Skill Loader Infra)]

文件职责：
1. 负责系统技能（Skills）的物理文件扫描、Frontmatter 解析和启用状态持久化配置。
2. 整合原 skills/loader/config.py 与 skills/loader/loader.py，消灭多余的 loader/ 子目录。

数据流向：
- 输入：物理技能文件的读取请求与配置变更。
- 输出：SkillSummary 对象列表、完整技能 Markdown 文本。
"""
from pathlib import Path
from typing import Optional
from backend.skills.types import SkillSummary
from backend.infra.config.settings import load_settings,save_settings

# --- 1. 配置契约与实体声明 ---


class SkillConfig:
    """保存禁用 skill 名单的配置对象。"""

    def __init__(self, disabled: set[str]):
        """输入：disabled 名称集合。输出：初始化后的 SkillConfig 实例。"""
        self.disabled = disabled


def load_skill_config() -> SkillConfig:
    """从 settings.json 的 skills.disabled 读取禁用的技能"""
    raw_data = load_settings()
    disabled_data = raw_data.get("skills", {}).get("disabled", [])
    disabled_names = set(disabled_data) if isinstance(disabled_data, list) else set()
    return SkillConfig(disabled=disabled_names)


def is_skill_disabled(skill_name: str, config: SkillConfig) -> bool:
    """输入：skill 名称、SkillConfig 对象。输出：这个 skill 是否在禁用名单里。"""
    return skill_name in config.disabled


def save_skill_config(config: SkillConfig) -> None:
    """更新 settings.json 中的技能配置"""
    settings = load_settings()
    if "skills" not in settings or not isinstance(settings["skills"], dict):
        settings["skills"] = {}
    settings["skills"]["disabled"] = sorted(config.disabled)
    save_settings(settings)


# --- 2. 动态技能文件扫描与解析基础设施 ---


def get_skills_roots() -> list[tuple[str, Path]]:
    """获取 skill 根目录列表，只从 settings.json 读取"""
    settings = load_settings()
    
    roots_cfg = settings.get("skills", {}).get("roots")
    if isinstance(roots_cfg, list):
        results = []
        for item in roots_cfg:
            if isinstance(item, dict) and "name" in item and "path" in item:
                results.append((str(item["name"]), Path(item["path"])))
        return results
    return []


def list_skills() -> list[SkillSummary]:
    """输出：合并启用状态后的 SkillSummary 列表。"""
    roots = get_skills_roots()
    config = load_skill_config()

    results: list[SkillSummary] = []

    for source_name, root_path in roots:
        if not root_path.exists():
            continue

        for skill_file in sorted(root_path.glob("*/SKILL.md")):
            summary = _load_skill_summary(skill_file, source_name, root_path)
            if summary.enabled and is_skill_disabled(summary.name, config):
                summary = summary.model_copy(update={"enabled": False})
            results.append(summary)

    return sorted(results, key=lambda item: item.name.lower())


def _load_skill_summary(
    skill_file: Path, source_name: str, root_path: Path
) -> SkillSummary:
    """输入：单个 SKILL.md 路径、来源名、来源根目录。输出：一个 SkillSummary。"""
    safe_path = skill_file.as_posix()

    try:
        content = skill_file.read_text(encoding="utf-8")
        metadata = _parse_frontmatter(content)
        name = str(metadata.get("name") or skill_file.parent.name)
        description_value = metadata.get("description")
        description = str(description_value) if description_value is not None else None

        return SkillSummary(
            name=name, description=description, path=safe_path, enabled=True
        )

    except Exception as exc:
        return SkillSummary(
            name=skill_file.parent.name,
            description=None,
            path=safe_path,
            enabled=False,
            error=str(exc),
        )


def _parse_frontmatter(content: str) -> dict[str, str]:
    """输入：SKILL.md 全文字符串。输出：frontmatter 键值字典。"""
    lines = content.splitlines()
    if len(lines) < 3 or lines[0].strip() != "---":
        raise ValueError("Missing frontmatter")

    metadata: dict[str, str] = {}

    for line in lines[1:]:
        if line.strip() == "---":
            return metadata

        if ":" not in line:
            raise ValueError(f"Invalid frontmatter line: {line}")

        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"').strip("'")

    raise ValueError("Frontmatter not closed")


def load_skill_content(skill_name: str) -> str:
    """输入：skill 名称。输出：目标 skill 的完整 SKILL.md 文本。"""
    roots = get_skills_roots()

    for _, root_path in roots:
        if not root_path.exists():
            continue

        for skill_file in sorted(root_path.glob("*/SKILL.md")):
            try:
                content = skill_file.read_text(encoding="utf-8")
                metadata = _parse_frontmatter(content)
            except Exception:
                continue

            current_name = str(metadata.get("name") or skill_file.parent.name)

            if current_name == skill_name:
                return content

    raise ValueError(f"Skill not found: {skill_name}")
