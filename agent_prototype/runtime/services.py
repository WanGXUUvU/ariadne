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
from datetime import datetime

from ..core.schemas import AgentInput, AgentOutput, AgentState, ResetInput,CompactInput,CompactOutput,RunMetadata,CreateSessionInput,SessionSummary
from ..storage.session_store import SqliteSessionStore
from .agent import Agent
from .agent_loader import load_agent_definition
from .skill_loader import list_skills,load_skill_content
from .prompt_builder  import build_skill_catalog_prompt,build_runtime_system_prompt
from .compaction import build_compact_prompt,compact_state_with_summary,split_messages_for_compaction
from .llm_client import call_llm

def build_reply_preview(reply: str, max_len: int = 120) -> str:
    """输入：完整回复文本、最大长度。输出：单行回复摘要字符串。"""

    # `split()` 会按任意空白拆分；再用空格 join，可把多余换行压成单行文本。
    text = " ".join(reply.split())
    return text[:max_len]

def create_session_service(payload:CreateSessionInput,db:Session)->SessionSummary:
    """输入：CreateSessionInput 请求对象、数据库会话。输出：新建 session 的摘要信息。"""  # 这个 service 负责创建空白 session，但不运行 agent

    store = SqliteSessionStore(db)
    session_id=uuid.uuid4().hex
    state=AgentState()

    try:
        record = store.upsert_session_snapshot(
            session_id,  # 把新生成的 session_id 写入主表
            state=state,  # 先存空 state，后续第一次 /run 再把消息填进去
            session_name=payload.session_name,  # 如果前端传了名字就用它；不传时 store 会回退到 session_id
            last_agent_name=None,  # 新建空会话时还没有运行过 agent
            last_skill_name=None,  # 新建空会话时也还没有使用任何 skill
            last_reply_preview=None,  # 没有回复，自然没有 reply preview
        )
        db.commit()  # 把新 session 真正提交到数据库
        db.refresh(record)  # 刷新 ORM 对象，确保 created_at / updated_at 等数据库字段可读
    except Exception:
        db.rollback()  # 如果创建失败，回滚这次事务，避免留下半成品
        raise

    return SessionSummary(
        session_id=record.session_id,  # 返回新建好的 session_id，前端后续靠它继续操作
        session_name=record.session_name,  # 返回最终生效的会话名；不传时通常会等于 session_id
        created_at=record.created_at,  # 返回创建时间，给列表页直接使用
        updated_at=record.updated_at,  # 新建时更新时间通常等于创建时间
        last_agent_name=record.last_agent_name,  # 空会话还没有最近 agent，应该是 None
        last_skill_name=record.last_skill_name,  # 空会话还没有最近 skill，应该是 None
        message_count=record.message_count,  # 空会话消息数应为 0
        last_reply_preview=record.last_reply_preview,  # 空会话没有最后回复摘要
    )
def run_agent_service(agent_input: AgentInput, db: Session) -> AgentOutput:
    """输入：AgentInput 请求对象、数据库会话。输出：AgentOutput 结果对象。

    这是 `/run` 的主业务入口，负责把：
    请求输入 -> agent 执行 -> session 快照 -> trace 落库
    串成一个闭环。
    """

    store = SqliteSessionStore(db)
    state = store.get(agent_input.session_id) or AgentState()  # 先读取当前 session 的状态；没有就新建空状态

    if state.messages:  # 只有已有历史消息时，才有必要尝试自动 compact
        auto_compact_result = compact_session_service(  # 先尝试对当前 session 做一次自动 compact
            CompactInput(
                session_id=agent_input.session_id,  # 自动 compact 仍然针对当前 session
                trigger_threshold=12,  # 第一版先写死默认阈值，后面再考虑配置化
                keep_recent_count=4,  # 第一版先写死默认 recent 保留数量
            ),
            db,
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

def compact_session_service(payload:CompactInput,db:Session)->CompactOutput:
    """输入 压缩前的CompactInput和 db 输出 压缩后的对象"""
    store = SqliteSessionStore(db)
    state = store.get(payload.session_id)

    if state is None:
        raise ValueError("Session not found")
    
    if len(state.messages) <=payload.trigger_threshold: #如果小于需要压缩的阈值
        return CompactOutput(state=state,did_compact=False,removed_count=0)
    
    _, middle_messages,_ = split_messages_for_compaction(  # 先把完整历史切成三段
        state.messages,  # 传入当前会话历史消息
        keep_recent_count=payload.keep_recent_count,  # 按请求里的 recent 保留数量切分
    )

    if not middle_messages:
        return CompactOutput(state=state,did_compact=False,removed_count=0)
    
    compact_prompt = build_compact_prompt(middle_messages)

    summary_response = call_llm(
        [{"role":"system","content":compact_prompt}],
        tools=None,
    )
    summary_text = summary_response.get("content","").strip()
    if not summary_text:
        raise ValueError("Compact summary is empty")
    
    compact_result = compact_state_with_summary(
    state=state,  # 传入原始会话状态
    summary_text=summary_text,  # 传入模型刚刚返回的 compact 摘要文本
    keep_recent_count=payload.keep_recent_count,  # 继续沿用这次 compact 的 recent 保留数量
)

    if not compact_result.did_compact:
        return compact_result
    
    record = store.read_session_record(payload.session_id)
    try:
        store.upsert_session_snapshot(
            payload.session_id,
            state=compact_result.state,
            session_name= record.session_name if record else payload.session_id,
            last_agent_name=record.last_agent_name if record else None,
            last_skill_name= record.last_skill_name if record else None,
            last_reply_preview= record.last_reply_preview if record else None,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return compact_result
def reset_session_service(payload: ResetInput, db: Session) -> dict[str, bool]:
    """输入：ResetInput 请求对象、数据库会话。输出：是否删除成功的结果字典。"""

    store = SqliteSessionStore(db)
    store.delete(payload.session_id)
    return {"ok": True}

