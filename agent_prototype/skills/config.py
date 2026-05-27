"""应用服务层 (Application Layer) - 技能元数据配置

职责：
1. 管理动态技能的系统存储路径、模块名转换和运行时缓存配置。
2. 维护物理技能插件在系统中的硬编码白名单与加载策略。

不负责：
1. 物理模块加载或技能状态管理。

数据流向：
- 输入：配置查询请求。
- 输出：技能存储与动态装配的物理配置。
- 上游来源：技能加载器（Loader）与技能服务。
- 下游流向：被 `loader.py` 与 `service.py` 强依赖。
"""

import json
from pathlib import Path
from typing import Optional

DEFAULT_PROTECTED_SKILL_NAMES = {"default"}  # 默认保护的 skill，防止被误禁用
SKILL_CONFIG_FILENAME = "skill-config.json"  # skill 配置文件名


class SkillConfig:
    """输入：disabled 名称集合。输出：保存禁用 skill 名单的配置对象。"""

    def __init__(self, disabled: set[str]):  # skill配置对象
        """输入：disabled 名称集合。输出：初始化后的 SkillConfig 实例。"""
        self.disabled = disabled


def get_default_skill_config_path() -> Path:  # 返回默认配置文件路径
    """输入：无。输出：默认 skill 配置文件路径。"""
    repo_root = Path(__file__).resolve().parents[2]  # 反推到仓库根目录
    return repo_root / ".agent" / SKILL_CONFIG_FILENAME  # 指向仓库内配置文件


def _normalize_name_set(values: object) -> set[str]:  # 把json数组转换成字符串集合
    """输入：任意 JSON 字段值。输出：过滤后的 skill 名称集合。"""
    if not isinstance(values, list):  # 这里传进来的是列表，所以继续
        return set()
    return {str(item) for item in values if str(item).strip()}


def load_skill_config(config_path: Optional[Path] = None) -> SkillConfig:  # 加载skill配置
    """输入：可选的配置文件路径。输出：SkillConfig 配置对象。"""
    path = config_path or get_default_skill_config_path()

    if not path.exists():
        return SkillConfig(disabled=set())

    try:
        raw_data = json.loads(path.read_text(encoding="utf-8"))  # "disabled": ["openai-docs", "python-debug"]
    except Exception:
        return SkillConfig(disabled=set())

    disabled_names = _normalize_name_set(raw_data.get("disabled"))  # 把JSON里的 disabled 数组规范成 set[str]
    return SkillConfig(disabled=disabled_names)  # SkillConfig(disabled={"openai-docs", "python-debug"})


def is_skill_disabled(skill_name: str, config: SkillConfig) -> bool:
    """输入：skill 名称、SkillConfig 对象。输出：这个 skill 是否在禁用名单里。"""
    return skill_name in config.disabled


def save_skill_config(config: SkillConfig, config_path: Optional[Path] = None) -> None:  # 把skill配置写回到配置文件
    """输入：SkillConfig 对象、可选的配置文件路径。输出：无，副作用是把配置写回磁盘。"""
    path = config_path or get_default_skill_config_path()

    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "disabled": sorted(config.disabled)
    }

    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )