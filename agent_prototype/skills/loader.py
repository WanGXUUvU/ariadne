"""
[九层模型 - L4 技能层 - 基础设施 (Skill Loader Infra)]

文件职责：
1. 负责系统技能（Skills）的物理文件扫描、Frontmatter 解析和启用状态持久化配置。
2. 整合原 skills/loader/config.py 与 skills/loader/loader.py，消灭多余的 loader/ 子目录。

数据流向：
- 输入：物理技能文件的读取请求与配置变更。
- 输出：SkillSummary 对象列表、完整技能 Markdown 文本。
"""

import json
import logging
import time as _time
from pathlib import Path
from typing import Optional
from agent_prototype.skills.types import SkillSummary

logger = logging.getLogger(__name__)

# --- 1. 配置契约与实体声明 ---
DEFAULT_PROTECTED_SKILL_NAMES = {"default"}  # 默认保护的 skill，防止被误禁用
SKILL_CONFIG_FILENAME = "skill-config.json"  # skill 配置文件名
_list_skills_cache: Optional[list] = None
_list_skills_cache_ts: float = 0.0
_LIST_SKILLS_TTL = 30


class SkillConfig:
    """保存禁用 skill 名单的配置对象。"""

    def __init__(self, disabled: set[str]):
        """输入：disabled 名称集合。输出：初始化后的 SkillConfig 实例。"""
        self.disabled = disabled


def get_default_skill_config_path() -> Path:
    """输入：无。输出：默认 skill 配置文件路径。"""
    repo_root = Path(__file__).resolve().parents[2]  # 反推至仓库根目录 (parents[2])
    return repo_root / ".agent" / SKILL_CONFIG_FILENAME


def _normalize_name_set(values: object) -> set[str]:
    """输入：任意 JSON 字段值。输出：过滤后的 skill 名称集合。"""
    if not isinstance(values, list):
        return set()
    return {str(item) for item in values if str(item).strip()}


def load_skill_config(config_path: Optional[Path] = None) -> SkillConfig:
    """输入：可选的配置文件路径。输出：SkillConfig 配置对象。"""
    path = config_path or get_default_skill_config_path()

    if not path.exists():
        return SkillConfig(disabled=set())

    try:
        raw_data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.warning(
            "Failed to parse skill config at %s, falling back to empty", path, exc_info=True
        )
        return SkillConfig(disabled=set())

    disabled_names = _normalize_name_set(raw_data.get("disabled"))
    return SkillConfig(disabled=disabled_names)


def is_skill_disabled(skill_name: str, config: SkillConfig) -> bool:
    """输入：skill 名称、SkillConfig 对象。输出：这个 skill 是否在禁用名单里。"""
    return skill_name in config.disabled


def save_skill_config(config: SkillConfig, config_path: Optional[Path] = None) -> None:
    """输入：SkillConfig 对象、可选的配置文件路径。输出：无，副作用是把配置写回磁盘并清除内存缓存。"""
    global _list_skills_cache, _list_skills_cache_ts
    path = config_path or get_default_skill_config_path()

    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {"disabled": sorted(config.disabled)}

    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    # 配置变更后立即失效缓存，确保下次 list_skills 重新读取
    _list_skills_cache = None
    _list_skills_cache_ts = 0.0


# --- 2. 动态技能文件扫描与解析基础设施 ---


def get_default_skill_roots() -> list[tuple[str, Path]]:
    """输入：无。输出：默认 skill 根目录列表。"""
    repo_root = Path(__file__).resolve().parents[2]  # 从当前文件反推至仓库根目录 (parents[2])
    package_root = Path(__file__).resolve().parents[1]  # 反推至 agent_prototype 根目录 (parents[1])
    home_root = Path.home()
    return [
        ("opencode", repo_root / ".opencode" / "skills"),
        ("agents", repo_root / ".agents" / "skills"),
        ("builtin", package_root / "skills"),
        ("user-codex", home_root / ".codex" / "skills"),
        ("user", home_root / ".agents" / "skills"),
    ]


def list_skills(
    skill_roots: Optional[list[tuple[str, Path]]] = None,
    config_path: Optional[Path] = None,
) -> list[SkillSummary]:
    """输入：可选的 skill 根目录列表、可选的配置文件路径。输出：合并启用状态后的 SkillSummary 列表。"""
    global _list_skills_cache, _list_skills_cache_ts
    use_cache = skill_roots is None and config_path is None
    if use_cache:
        now = _time.monotonic()
        if _list_skills_cache is not None and now - _list_skills_cache_ts < _LIST_SKILLS_TTL:
            return _list_skills_cache

    roots = skill_roots or get_default_skill_roots()
    if config_path is not None or skill_roots is None:
        config = load_skill_config(config_path)
    else:
        config = SkillConfig(disabled=set())

    results: list[SkillSummary] = []

    for source_name, root_path in roots:
        if not root_path.exists():
            continue

        for skill_file in sorted(root_path.glob("*/SKILL.md")):
            summary = _load_skill_summary(skill_file, source_name, root_path)
            if summary.enabled and is_skill_disabled(summary.name, config):
                summary = summary.model_copy(update={"enabled": False})
            results.append(summary)

    result = sorted(results, key=lambda item: item.name.lower())

    if use_cache:
        _list_skills_cache = result
        _list_skills_cache_ts = _time.monotonic()

    return result


def _load_skill_summary(skill_file: Path, source_name: str, root_path: Path) -> SkillSummary:
    """输入：单个 SKILL.md 路径、来源名、来源根目录。输出：一个 SkillSummary。"""
    safe_relative_path = skill_file.relative_to(root_path).as_posix()
    safe_path = f"{source_name}/{safe_relative_path}"

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


def load_skill_content(
    skill_name: str, skill_roots: Optional[list[tuple[str, Path]]] = None
) -> str:
    """输入：skill 名称、可选的 skill 根目录列表。输出：目标 skill 的完整 SKILL.md 文本。"""
    roots = skill_roots or get_default_skill_roots()

    for _, root_path in roots:
        if not root_path.exists():
            continue

        for skill_file in sorted(root_path.glob("*/SKILL.md")):
            try:
                content = skill_file.read_text(encoding="utf-8")
                metadata = _parse_frontmatter(content)
            except Exception:
                logger.warning("Failed to parse skill file %s, skipping", skill_file, exc_info=True)
                continue

            current_name = str(metadata.get("name") or skill_file.parent.name)

            if current_name == skill_name:
                return content

    raise ValueError(f"Skill not found: {skill_name}")
