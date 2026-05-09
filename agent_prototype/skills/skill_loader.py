from pathlib import Path
from typing import Optional
import json

from ..core.schemas import SkillSummary

def get_default_skill_roots()->list[tuple[str,Path]]: #返回默认要扫描的skill的根目录
    """输入：无。输出：默认 skill 根目录列表。"""
    repo_root=Path(__file__).resolve().parents[2] #从当前文件反推到仓库根目录
    package_root=Path(__file__).resolve().parents[1] #反推到agent_prototype根目录
    home_root=Path.home() #全局目录
    return [  # 返回“来源标签 + 实际路径”，方便后面做安全 path
        ("opencode", repo_root / ".opencode" / "skills"),  # 项目内 opencode skills 目录
        ("agents", repo_root / ".agents" / "skills"),  # 项目内 agents skills 目录
        ("builtin", package_root / "skills"),  # 应用内置 skills 目录
        ("user-codex", home_root /".codex" / "skills"), #用户级skill
        ("user", home_root /".agents" / "skills"),

    ]


def list_skills(
        skill_roots:Optional[list[tuple[str,Path]]]=None,
        config_path:Optional[Path]=None,
        )->list[SkillSummary]:
    """输入：可选的 skill 根目录列表、可选的配置文件路径。输出：合并启用状态后的 SkillSummary 列表。"""
    roots=skill_roots or get_default_skill_roots()# 没传目录时，使用默认 skill 扫描目录
    config = load_skill_config(config_path)# 先读取 skill 配置，拿到 disabled 名单
    results:list[SkillSummary]=[] #返回的结果

    for source_name,root_path in roots: #逐个扫描每个目录
        if not root_path.exists():#目录不存在直接提哦啊过
            continue

        for skill_file in sorted(root_path.glob("*/SKILL.md")):#只匹配一级目录下的SKILL.md
            summary = _load_skill_summary(skill_file, source_name, root_path)  # 先按原逻辑解析出一个 SkillSummary
            if summary.enabled and is_skill_disabled(summary.name,config):
                summary = summary.model_copy(update={"enabled": False})  # 命中 disabled 名单时，把 enabled 改成 False
            
            results.append(summary)   #逐个读取摘要  
        
    return sorted(results, key=lambda item: item.name.lower())


def _load_skill_summary(skill_file:Path,source_name:str,root_path:Path)->SkillSummary:
    """输入：单个 SKILL.md 路径、来源名、来源根目录。输出：一个 SkillSummary。"""
    safe_relative_path=skill_file.relative_to(root_path).as_posix()#先算相对路径 /Users/haoyu/.agent/skills/python_debug/SKILL.md
    safe_path=f"{source_name}/{safe_relative_path}"#给前端返回“来源+相对路径” user/python_debug/SKILL.md

    try:
        content=skill_file.read_text(encoding="utf-8")
        metadata=_parse_frontmatter(content)
        name=str(metadata.get("name") or skill_file.parent.name)
        description_value=metadata.get("description")
        description=str(description_value) if description_value is not None else None
        
        return SkillSummary(name=name,description=description,path=safe_path,enabled=True)

    except Exception as exc:
        return SkillSummary(
            name=skill_file.parent.name,
            description=None,
            path=safe_path,
            enabled=False,
            error=str(exc)
        )


def _parse_frontmatter(content:str)->dict[str,str]:#从SKILL.md提取frontmatter字段
    """输入：SKILL.md 全文字符串。输出：frontmatter 键值字典。"""
    lines =content.splitlines()#按行拆

    if len(lines)<3 or lines[0].strip()!="---":#没有frontmatter视为坏的skill
        raise ValueError("Missing frontmatter")
    
    metadata:dict[str,str]={} #存解析出来的键值对

    for line in lines[1:]:#从第二行开始读frontmatter 内容
        if line.strip()=="---":
            return metadata 
        
        if ":" not in line:#frontmatter 行至少要有 key: value
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

DEFAULT_PROTECTED_SKILL_NAMES = {"default"}  # 默认保护的 skill，防止被误禁用
SKILL_CONFIG_FILENAME = "skill-config.json"  # skill 配置文件名

def get_default_skill_config_path() -> Path:  # 返回默认配置文件路径
    """输入：无。输出：默认 skill 配置文件路径。"""
    repo_root = Path(__file__).resolve().parents[2]  # 反推到仓库根目录
    return repo_root / ".agent" / SKILL_CONFIG_FILENAME  # 指向仓库内配置文件

def _normalize_name_set(values:object)->set[str]:#把json数组转换成字符串集合
    """输入：任意 JSON 字段值。输出：过滤后的 skill 名称集合。"""
    if not isinstance(values,list): #这里传进来的是列表，所以继续
        return set()
    return {str(item) for item in values if str(item).strip()}

class SkillConfig:
    """输入：disabled 名称集合。输出：保存禁用 skill 名单的配置对象。"""

    def __init__(self,disabled:set[str]):#skill配置对象
        """输入：disabled 名称集合。输出：初始化后的 SkillConfig 实例。"""
        self.disabled=disabled

def load_skill_config(config_path:Optional[Path]=None)->SkillConfig:#加载skill配置
    """输入：可选的配置文件路径。输出：SkillConfig 配置对象。"""
    path = config_path or get_default_skill_config_path()

    if not path.exists():
        return SkillConfig(disabled=set())
    
    try:
        raw_data = json.loads(path.read_text(encoding="utf-8"))# "disabled": ["openai-docs", "python-debug"]
    except Exception:
        return SkillConfig(disabled=set())
    
    disabled_names = _normalize_name_set(raw_data.get("disabled")) #把JSON里的 disabled 数组规范成 set[str]
    return SkillConfig(disabled=disabled_names) #SkillConfig(disabled={"openai-docs", "python-debug"})

def is_skill_disabled(skill_name:str,config:SkillConfig)->bool:
    """输入：skill 名称、SkillConfig 对象。输出：这个 skill 是否在禁用名单里。"""
    return skill_name in config.disabled

def save_skill_config(config:SkillConfig,config_path:Optional[Path]=None)->None:#把skill配置写回到配置文件
    """输入：SkillConfig 对象、可选的配置文件路径。输出：无，副作用是把配置写回磁盘。"""
    path = config_path or get_default_skill_config_path()

    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "disabled": sorted(config.disabled)
    }

    path.write_text(
        json.dumps(payload,ensure_ascii=False,indent=2),
        encoding="utf-8",
    )
