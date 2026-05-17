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
from typing import Iterator,Optional,AsyncIterator

from ..core.schemas import AgentInput, AgentOutput, AgentState, RunMetadata,StreamFrame,AgentEvent  # /run 相关 schema  # 这一行负责输入输出类型
from ..storage.stores.session_store import SqliteSessionStore  # session 持久化仓库  # 这一行负责读写 session 状态
from ..runtime.agent_runtime import Agent  # Agent 执行器  # 这一行负责跑主循环
from ..skills.skill_loader import list_skills, load_skill_content  # 保持原有 patch 目标和兼容面
from .skill_context_service import build_runtime_definition_with_skills
from .agent_definition_service import load_agent_definition  # 加载 agent 定义  # 这一行负责 agent 配置
from .compact_service import _compact_in_memory  # 自动 compact 内存计算  # 这一行把压缩逻辑交给独立文件
from ..model.openai_adapter import ChatCompletionsAdapter

RUN_MODEL = os.getenv("RUN_MODEL", "deepseek-v4-flash")


def build_reply_preview(reply: str, max_len: int = 120) -> str:
    """输入：完整回复文本、最大长度。输出：单行回复摘要字符串。"""

    # `split()` 会按任意空白拆分；再用空格 join，可把多余换行压成单行文本。
    text = " ".join(reply.split())
    return text[:max_len]


def _prepare_run_context(agent_input: AgentInput, db: Session) -> tuple[AgentState, str, str]:
    """输入：AgentInput 请求对象、数据库会话。输出：运行前准备好的 state、runtime definition、agent 名称。"""

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
    runtime_definition = build_runtime_definition_with_skills(
        definition,
        agent_input,
        list_skills=list_skills,
        load_skill_content=load_skill_content,
    )

    return state, runtime_definition, effective_agent_name


def _persist_run_result(
    store: SqliteSessionStore,
    db: Session,
    agent_input: AgentInput,
    output: AgentOutput,
    effective_agent_name: str,
    run_id: str,
) -> AgentOutput:
    """输入：session 仓库、数据库会话、请求对象、执行结果、agent 名称、run_id。输出：补齐 metadata 后的 AgentOutput。"""

    metadata = RunMetadata(
        session_id=agent_input.session_id,
        run_id=run_id,
        agent_name=effective_agent_name,
        skill_name=agent_input.skill_name,
    )
    output = output.model_copy(update={"metadata": metadata})

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
        store.update_run_status(run_id=run_id, status="completed")
        db.commit()
    except Exception:
        # 两类数据要么一起成功，要么一起失败，避免只保存了一半。
        db.rollback()
        raise

    return output

def run_agent_service(agent_input: AgentInput, db: Session) -> AgentOutput:
    """输入：AgentInput 请求对象、数据库会话。输出：AgentOutput 结果对象。

    这是 `/run` 的主业务入口，负责把：
    请求输入 -> agent 执行 -> session 快照 -> trace 落库
    串成一个闭环。
    """

    store = SqliteSessionStore(db)
    state, runtime_definition, effective_agent_name = _prepare_run_context(agent_input, db)
    agent = Agent(
        state=state,
        definition=runtime_definition,
        allow_tool_names=runtime_definition.tool_names,
        model_adapter=ChatCompletionsAdapter(model=RUN_MODEL),
    )

    # `uuid4().hex` 生成 32 位十六进制字符串，适合作为当前 run 的唯一标识。
    run_id = uuid.uuid4().hex

    output = agent.run(agent_input)
    output.state.agent_name = effective_agent_name
    return _persist_run_result(
        store=store,
        db=db,
        agent_input=agent_input,
        output=output,
        effective_agent_name=effective_agent_name,
        run_id=run_id,
    )

def stream_agent_service(agent_input:AgentInput,db:Session)->Iterator[str]:

    store = SqliteSessionStore(db)
    state, runtime_definition, effective_agent_name = _prepare_run_context(agent_input, db)
    agent = Agent(
        state=state,
        definition=runtime_definition,
        allow_tool_names=runtime_definition.tool_names,
        model_adapter=ChatCompletionsAdapter(model=RUN_MODEL),
    )
    run_id = uuid.uuid4().hex
    yield _sse_frame(StreamFrame(
        type="start",
        data={"session_id":agent_input.session_id,"run_id":run_id,
            "agent_name":effective_agent_name,"skill_name":agent_input.skill_name}
    ))

    events:list[AgentEvent]=[]
    raw_reply=""

    for item in agent.stream_run(agent_input):
        if isinstance(item,str):
            raw_reply+=item
            yield _sse_frame(StreamFrame(type="delta",data={"content":item}))
        elif isinstance(item,AgentEvent):
            events.append(item)
            yield _sse_frame(StreamFrame(type="agent_event",data=item.model_dump()))

    output = AgentOutput(
        reply=raw_reply,           # streaming 结束后攒出的完整文字
        state=agent.state,         # agent 执行完后的最新 state
        events=events,             # 攒出的所有 AgentEvent 列表
        metadata=RunMetadata(
            session_id=agent_input.session_id,
            run_id=run_id,
            agent_name=effective_agent_name,
            skill_name=agent_input.skill_name,
        )
    )
    output.state.agent_name = effective_agent_name

    _persist_run_result(
        store=store,
        db=db,
        agent_input=agent_input,
        output=output,
        effective_agent_name=effective_agent_name,
        run_id=run_id,
    )
    yield _sse_frame(StreamFrame(
        type="end",
        data={
            "reply": raw_reply,
            "state": agent.state.model_dump(),
            "metadata": output.metadata.model_dump(),
        }
    ))

async def async_stream_agent_service(agent_input:AgentInput,db:Session)->AsyncIterator[str]:

    store = SqliteSessionStore(db)
    run_id = uuid.uuid4().hex
    def on_tool_start(tool_name, tool_call_id, input_json):
        record_id = store.create_tool_call(
            run_id=run_id,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            input_json=input_json,
        )
        db.flush()
        return record_id

    def on_tool_finish(record_id, status, result_json):
        store.finish_tool_call(
            record_id=record_id,
            status=status,
            result_json=result_json,
        )
        db.commit()
    state, runtime_definition, effective_agent_name = _prepare_run_context(agent_input, db)
    agent = Agent(
        state=state,
        definition=runtime_definition,
        allow_tool_names=runtime_definition.tool_names,
        model_adapter=ChatCompletionsAdapter(model=RUN_MODEL),
    )

    completed=False
    partial_reply=""
    try:
        yield _sse_frame(StreamFrame(
            type="start",
            data={"session_id":agent_input.session_id,"run_id":run_id,
                "agent_name":effective_agent_name,"skill_name":agent_input.skill_name}
        ))

        events:list[AgentEvent]=[]

        async for item in agent.async_stream_run(agent_input,on_tool_start=on_tool_start,on_tool_finish=on_tool_finish,):
            if isinstance(item,str):
                partial_reply+=item
                yield _sse_frame(StreamFrame(type="delta",data={"content":item}))
            elif isinstance(item,AgentEvent):
                events.append(item)
                yield _sse_frame(StreamFrame(type="agent_event",data=item.model_dump()))

        output = AgentOutput(
            reply=partial_reply,           # streaming 结束后攒出的完整文字
            state=agent.state,         # agent 执行完后的最新 state
            events=events,             # 攒出的所有 AgentEvent 列表
            metadata=RunMetadata(
                session_id=agent_input.session_id,
                run_id=run_id,
                agent_name=effective_agent_name,
                skill_name=agent_input.skill_name,
            )
        )
        output.state.agent_name = effective_agent_name

        _persist_run_result(
            store=store,
            db=db,
            agent_input=agent_input,
            output=output,
            effective_agent_name=effective_agent_name,
            run_id=run_id,
        )
        yield _sse_frame(StreamFrame(
            type="end",
            data={
                "reply": partial_reply,
                "state": agent.state.model_dump(),
                "metadata": output.metadata.model_dump(),
            }
        ))
        completed=True
    
    finally:
        if not completed:
            try:
                finalize_run_service(
                    session_id=agent_input.session_id,
                    run_id=run_id,
                    user_input=agent_input.user_input,
                    partial_reply=partial_reply,
                    agent_name=effective_agent_name,
                    skill_name=agent_input.skill_name,
                    db=db,
                )
            except Exception:
                pass

def _sse_frame(frame: StreamFrame) -> str:
    """把 StreamFrame 转成 SSE 协议格式的字符串。"""
    return f"data: {frame.model_dump_json()}\n\n"

def finalize_run_service(
    session_id: str,
    run_id: str,
    user_input: str,
    partial_reply: str,
    agent_name: Optional[str],
    skill_name: Optional[str],
    db: Session,
) -> dict[str, bool]:
    store = SqliteSessionStore(db)
    state = store.get(session_id) or AgentState()
    try:
        store.save_partial_run(
            session_id=session_id,
            run_id=run_id,
            agent_name=agent_name,
            skill_name=skill_name,
            user_input=user_input,
            partial_reply=partial_reply,
            state=state,
        )
        store.update_run_status(run_id=run_id, status="cancelled")
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"ok": True}

def get_run_detail_service(session_id: str, run_id: str, db):
    store = SqliteSessionStore(db)
    run, tool_calls = store.get_run_detail(run_id)
    if not run or run.session_id != session_id:
        return None, []
    return run, tool_calls
