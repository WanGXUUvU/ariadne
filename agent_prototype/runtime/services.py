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
    agent = Agent(
        state=state,
        definition=definition,
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
            last_skill_name=None,
            last_reply_preview=build_reply_preview(output.reply),
        )
        store.save_run_trace(
            session_id=agent_input.session_id,
            run_id=run_id,
            agent_name=effective_agent_name,
            skill_name=None,
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
