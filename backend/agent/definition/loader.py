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
- 上游来源：backend/agent/definition/service.py 触发。
- 下游流向：本地磁盘物理文件读取及正则格式匹配。
"""

from pathlib import Path
from typing import Optional
import yaml
from backend.agent.types import AgentDefinition

_BUILTIN_AGENTS_DIR = (
    Path(__file__).resolve().parent.parent.parent / "prompt" / "templates" / "system"
)


def list_builtin_agents() -> list[AgentDefinition]:
    """这个函数是用来从本地磁盘中扫描并加载所有系统内置 Agent（从 prompt/templates/system/*.md 物理文件里）的。

    需要拿到的东西：
    - 无需传入参数。

    会给出来的结果：
    - 扫描并解析成功后的内置 AgentDefinition 对象列表。
    """
    results = []
    if not _BUILTIN_AGENTS_DIR.exists():
        return results

    for md_file in sorted(_BUILTIN_AGENTS_DIR.glob("*.md")):
        agent = _load_agent_md(md_file)
        if agent:
            results.append(agent)
    return results


def _load_agent_md(md_file: Path) -> Optional[AgentDefinition]:
    """这个私有函数是用来解析单个 .md 格式的内置 Agent 文件，并把它转化为 Python 的 AgentDefinition 对象的。

    它会读取 Markdown 文件的头部 YAML 配置（比如名字、描述、限制工具等）以及 Markdown 的正文（作为系统提示词模板 system_prompt）。

    需要拿到的东西：
    - md_file: Path 对象，指明要读取的 Markdown 文件的磁盘路径。

    会给出来的结果：
    - 解析成功的话返回 AgentDefinition 配置对象，要是解析失败或格式不对则优雅地返回 None。
    """

    try:
        content = md_file.read_text(encoding="utf-8")
        frontmatter, body = _parse_md(content)

        agent_id = md_file.stem
        return AgentDefinition(
            id=agent_id,
            name=frontmatter.get("name") or agent_id,
            description=frontmatter.get("description"),
            tool_names=frontmatter.get("tool_names"),
            system_prompt=body.strip() or "你是一个助手",
        )
    except Exception:
        return None


def _parse_md(content: str) -> tuple[dict, str]:
    """这个私有辅助函数是用来把一个 Markdown 文本的内容拆分成"头部 YAML 元数据"和"剩余正文"两部分的。

    很多 Markdown 文件会在开头用 --- 包裹一些 key-value 属性，这个函数就是负责把它们切开。

    需要拿到的东西：
    - content: 字符串，整个 Markdown 文件的全部文本内容。

    会给出来的结果：
    - 一个元组 (frontmatter, body)，其中 frontmatter 是一个解析后的 YAML 配置字典，body 是过滤掉头部信息后的干净正文文本。
    """

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
