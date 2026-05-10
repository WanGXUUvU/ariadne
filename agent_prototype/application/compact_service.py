import os

from sqlalchemy.orm import Session  # 数据库会话类型  # 这一行负责事务上下文

from ..core.schemas import AgentState, CompactInput, CompactOutput,ChatMessage  # compact 相关 schema  # 这一行负责输入输出类型
from ..storage.stores.session_store import SqliteSessionStore  # session 持久化仓库  # 这一行负责读写数据库记录
from ..context.compaction import build_compact_prompt, compact_state_with_summary, split_messages_for_compaction  # compact 相关工具  # 这一行负责消息压缩算法
from ..model.openai_adapter import ChatCompletionsAdapter
from ..model.model_types import ModelConfig, ModelRequest

COMPACT_MODEL = os.getenv("COMPACT_MODEL", "deepseek-v4-flash")


def _compact_in_memory(
    state: AgentState,
    trigger_threshold: int,
    keep_recent_count: int,
) -> CompactOutput:
    """输入：当前会话 state、触发阈值、recent 保留数量。输出：只在内存中计算出的 compact 结果。"""  # 这个内部函数只负责“算 compact”，不负责写库或提交事务

    if len(state.messages) <= trigger_threshold:  # 如果当前消息数还没达到触发阈值，就不用压缩
        return CompactOutput(state=state, did_compact=False, removed_count=0)  # 原样返回，不产生任何副作用

    _, middle_messages, _ = split_messages_for_compaction(
        state.messages,  # 把完整消息切成锚点、中段、recent 三段
        keep_recent_count=keep_recent_count,  # recent 保留数量继续由调用方控制
    )

    if not middle_messages:  # 如果没有中段消息，说明没有真正可压缩的主体
        return CompactOutput(state=state, did_compact=False, removed_count=0)  # 直接返回不压缩结果

    compact_prompt = build_compact_prompt(middle_messages)  # 用中段消息拼出 compact 提示词

    adapter = ChatCompletionsAdapter(model=COMPACT_MODEL)
    request = ModelRequest(
        messages=[
            ChatMessage(role="system", content=compact_prompt),
        ],
        tools=[],
        config=ModelConfig(stream=False),
        metadata={"mode": "compact"},
    )
    summary_response = adapter.generate(request)
    summary_text = (summary_response.content or "").strip()


    if not summary_text:  # 如果模型没有产出有效摘要
        raise ValueError("Compact summary is empty")  # 抛业务错误，阻止后续写入空摘要

    return compact_state_with_summary(
        state=state,  # 基于原始 state 生成 compact 后的新 state
        summary_text=summary_text,  # 用模型摘要替换中段历史
        keep_recent_count=keep_recent_count,  # 保持 recent 截断策略一致
    )

def compact_session_service(payload:CompactInput,db:Session)->CompactOutput:
    """输入 压缩前的CompactInput和 db 输出 压缩后的对象"""
    store = SqliteSessionStore(db)
    state = store.get(payload.session_id)

    if state is None:
        raise ValueError("Session not found")
    
    compact_result = _compact_in_memory(
        state=state,
        trigger_threshold=payload.trigger_threshold,
        keep_recent_count=payload.keep_recent_count,
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
