"""应用服务层 (Application Layer) - 内置 Agent 定义加载器

职责：
1. 从本地 Markdown (.md) 格式描述文件中物理提取并解析内置 Agent 定义。
2. 解析描述文件中的系统提示词模板、工具列表和元数据信息。

不负责：
1. 自定义 Agent 的 CRUD 持久化或数据库接口。
2. 运行时 Agent 运行状态的维护。

数据流向：
- 输入：本地 Markdown 物理描述文件。
- 输出：AgentDefinition 系统内置定义对象。
- 上游来源：agent_prototype/agent/definition_service.py 触发。
- 下游流向：本地磁盘物理文件读取及正则格式匹配。
"""

from pathlib import Path
from typing import Optional
import yaml
from agent_prototype.agent.definition import AgentDefinition

_BUILTIN_AGENTS_DIR = Path(__file__).resolve().parent.parent / "prompt" / "templates" / "system"

def list_builtin_agents()->list[AgentDefinition]:
    """扫描agents 目录 返回内置的AgentDefinition列表"""
    results=[]
    if not _BUILTIN_AGENTS_DIR.exists():
        return results
    
    for md_file in sorted(_BUILTIN_AGENTS_DIR.glob("*.md")):
        agent=_load_agent_md(md_file)
        if agent:
            results.append(agent)
    return results

def _load_agent_md(md_file:Path)->Optional[AgentDefinition]:
        """解析单个 .md 文件，返回 AgentDefinition，失败返回 None"""

        try:
            content=md_file.read_text(encoding="utf-8")
            frontmatter,body=_parse_md(content)

            agent_id=md_file.stem
            return AgentDefinition(
                id=agent_id,
                name=frontmatter.get("name") or agent_id,
                description=frontmatter.get("description"),
                tool_names=frontmatter.get("tool_names"),
                system_prompt=body.strip() or "你是一个助手"
            )
        except Exception:
            return None


def _parse_md(content:str)->tuple[dict,str]:
    """拆分 frontmatter 和 body"""

    if not content.startswith("---"):
        return {},content
    # 找第二个 ---
    end = content.find("\n---",3)
    if end ==-1:
        return {},content

    fm_text=content[3:end].strip()
    body=content[end+4:]

    frontmatter=yaml.safe_load(fm_text) or {}
    return frontmatter,body