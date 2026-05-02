"""运行时业务编排层。

这个文件负责把多个底层组件串起来：
- 读取 / 更新 session 状态
- 选择 agent 定义
- 调用 Agent 执行
- 持久化 session 快照和 trace

这里是“业务流程”发生的地方，不直接暴露 HTTP，也不直接定义 ORM 表结构。
"""

import uuid

from sqlalchemy.orm import Session

from ..core.schemas import AgentInput, AgentOutput, AgentState, ResetInput
from ..storage.session_store import SqliteSessionStore
from .agent import Agent
from .agent_loader import load_agent_definition
from .skill_loader import list_skills,load_skill_content
from .prompt_builder  import build_skill_catalog_prompt,build_runtime_system_prompt

def build_reply_preview(reply: str, max_len: int = 120) -> str:
    """生成 session 列表里展示用的回复摘要。"""

    # `split()` 会按任意空白拆分；再用空格 join，可把多余换行压成单行文本。
    text = " ".join(reply.split())
    return text[:max_len]


def run_agent_service(agent_input: AgentInput, db: Session) -> AgentOutput:
    """执行一次 agent run，并负责把结果持久化。

    这是 `/run` 的主业务入口，负责把：
    请求输入 -> agent 执行 -> session 快照 -> trace 落库
    串成一个闭环。
    """

    store = SqliteSessionStore(db)
    state = store.get(agent_input.session_id) or AgentState()

    effective_agent_name = agent_input.agent_name or "default"
    definition = load_agent_definition(effective_agent_name, db)
    skills=list_skills()# 先拿到所有本地 skill 的摘要列表
    skill_catalog_prompt=build_skill_catalog_prompt(skills)# 把摘要列表拼成给模型看的 skill 目录
    selected_skill_content=None# 默认这轮不加载任何 skill 正文
    if agent_input.skill_name:  # 如果这轮请求显式指定了某个 skill
        selected_skill_content=load_skill_content(agent_input.skill_name)#在加载SKILL.md
    runtime_system_prompt=build_runtime_system_prompt(
        definition.system_prompt,skill_catalog_prompt,selected_skill_content,
    )
    runtime_definition = definition.model_copy(
        update={"system_prompt": runtime_system_prompt}  # 复制一个本轮临时 definition，只替换 system prompt
    )
    agent = Agent(
        state=state,
        definition=runtime_definition,
        allow_tool_names=definition.tool_names,
    )

    # `uuid4().hex` 生成 32 位十六进制字符串，适合作为当前 run 的唯一标识。
    run_id = uuid.uuid4().hex

    output = agent.run(agent_input)
    output = output.model_copy(update={"run_id": run_id})
    output.state.agent_name = effective_agent_name

    try:
        store.upsert_session_snapshot(
            agent_input.session_id,
            state=output.state,
            last_agent_name=effective_agent_name,
            last_skill_name=agent_input.skill_name,
            last_reply_preview=build_reply_preview(output.reply),
        )
        store.save_run_trace(
            session_id=agent_input.session_id,
            run_id=run_id,
            agent_name=effective_agent_name,
            skill_name=agent_input.skill_name,
            user_input=agent_input.user_input,
            reply=output.reply,
            events=output.events,
        )
        db.commit()
    except Exception:
        # 两类数据要么一起成功，要么一起失败，避免只保存了一半。
        db.rollback()
        raise

    return output


def reset_session_service(payload: ResetInput, db: Session) -> dict[str, bool]:
    """删除某个 session 的持久化记录。"""

    store = SqliteSessionStore(db)
    store.delete(payload.session_id)
    return {"ok": True}
