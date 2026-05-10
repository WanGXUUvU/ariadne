"""运行时业务编排层。

这个文件负责把多个底层组件串起来：
- 读取 / 更新 session 状态
- 选择 agent 定义
- 调用 Agent 执行
- 持久化 session 快照和 trace

这里是“业务流程”发生的地方，不直接暴露 HTTP，也不直接定义 ORM 表结构。
"""

import os
import uuid  # 生成 run_id  # 这一行负责唯一标识
from sqlalchemy.orm import Session  # 数据库会话类型  # 这一行负责事务上下文

from ..core.schemas import AgentInput, AgentOutput, AgentState, RunMetadata  # /run 相关 schema  # 这一行负责输入输出类型
from ..storage.stores.session_store import SqliteSessionStore  # session 持久化仓库  # 这一行负责读写 session 状态
from ..runtime.agent_runtime import Agent  # Agent 执行器  # 这一行负责跑主循环
from .agent_definition_service import load_agent_definition  # 加载 agent 定义  # 这一行负责 agent 配置
from ..skills.skill_loader import list_skills, load_skill_content  # skill 列表和正文加载  # 这一行负责 skill 相关数据
from ..context.prompt_builder import build_skill_catalog_prompt, build_runtime_system_prompt  # 构造 prompt  # 这一行负责 prompt 组装
from .compact_service import _compact_in_memory  # 自动 compact 内存计算  # 这一行把压缩逻辑交给独立文件
from ..model.openai_adapter import ChatCompletionsAdapter

RUN_MODEL = os.getenv("RUN_MODEL", "deepseek-v4-flash")


def build_reply_preview(reply: str, max_len: int = 120) -> str:
    """输入：完整回复文本、最大长度。输出：单行回复摘要字符串。"""

    # `split()` 会按任意空白拆分；再用空格 join，可把多余换行压成单行文本。
    text = " ".join(reply.split())
    return text[:max_len]

def run_agent_service(agent_input: AgentInput, db: Session) -> AgentOutput:
    """输入：AgentInput 请求对象、数据库会话。输出：AgentOutput 结果对象。

    这是 `/run` 的主业务入口，负责把：
    请求输入 -> agent 执行 -> session 快照 -> trace 落库
    串成一个闭环。
    """

    store = SqliteSessionStore(db)
    state = store.get(agent_input.session_id) or AgentState()  # 先读取当前 session 的状态；没有就新建空状态

    if state.messages:  # 只有已有历史消息时，才有必要尝试自动 compact
        auto_compact_result = _compact_in_memory(
            state=state,  # 直接把当前内存里的 state 传进去做 compact 计算
            trigger_threshold=12,  # 自动 compact 继续沿用当前默认触发阈值
            keep_recent_count=2,  # 自动 compact 继续保留最近 2 条原始消息
        )
        state = auto_compact_result.state  # 自动 compact 后，后续统一使用返回的最新 state



    effective_agent_name = agent_input.agent_name or "default"
    definition = load_agent_definition(effective_agent_name, db)
    skills=list_skills()# 先拿到所有本地 skill 的摘要列表
    skill_catalog_prompt=build_skill_catalog_prompt(skills)# 把摘要列表拼成给模型看的 skill 目录
    selected_skill_content=None# 默认这轮不加载任何 skill 正文
    if agent_input.skill_name:  # 如果这轮请求显式指定了某个 skill
        selected_skill=next(#从当前skill列表查找指定的skill
            (skill for skill in skills if skill.name==agent_input.skill_name),
            None,
        )
        if selected_skill is None:
            raise ValueError(f"Skill not found:{agent_input.skill_name}")
        
        if not selected_skill.enabled:
            raise ValueError(f"Skill is disabled:{agent_input.skill_name}")
        
        selected_skill_content=load_skill_content(agent_input.skill_name)
        
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
        model_adapter=ChatCompletionsAdapter(model=RUN_MODEL),
    )

    # `uuid4().hex` 生成 32 位十六进制字符串，适合作为当前 run 的唯一标识。
    run_id = uuid.uuid4().hex

    output = agent.run(agent_input)
    output.state.agent_name = effective_agent_name

    metadata=RunMetadata(
        session_id=agent_input.session_id,
        run_id=run_id,
        agent_name=effective_agent_name,
        skill_name=agent_input.skill_name,
    )
    output=output.model_copy(update={"metadata":metadata})
    
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
