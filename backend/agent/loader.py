"""加载内置 Agent 定义。"""

from pathlib import Path
from typing import Optional
import yaml
from backend.agent.types import AgentDefinition

_BUILTIN_AGENTS_DIR = (
    Path(__file__).resolve().parent.parent / "prompt" / "templates" / "system"
)


def list_builtin_agents() -> list[AgentDefinition]:
    """扫描并加载所有内置 Agent。"""
    results = []
    if not _BUILTIN_AGENTS_DIR.exists():
        return results

    for md_file in sorted(_BUILTIN_AGENTS_DIR.glob("*.md")):
        agent = _load_agent_md(md_file)
        if agent:
            results.append(agent)
    return results


def _load_agent_md(md_file: Path) -> Optional[AgentDefinition]:
    """解析单个内置 Agent Markdown 文件。"""

    try:
        content = md_file.read_text(encoding="utf-8")
        frontmatter, body = _parse_md(content)

        agent_id = md_file.stem
        return AgentDefinition(
            id=agent_id,
            name=frontmatter.get("name") or agent_id,
            description=frontmatter.get("description"),
            tool_names=frontmatter.get("tool_names"),
            system_prompt=body.strip(),
        )
    except Exception:
        return None


def _parse_md(content: str) -> tuple[dict, str]:
    """拆分 Markdown frontmatter 和正文。"""

    if not content.startswith("---"):
        return {}, content
    # 找第二个 ---
    end = content.find("\n---", 3)
    if end == -1:
        return {}, content

    fm_text = content[3:end].strip()
    body = content[end + 4 :]

    frontmatter = yaml.safe_load(fm_text) or {}
    return frontmatter, body
