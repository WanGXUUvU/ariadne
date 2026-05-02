"""FastAPI 路由层。

这个文件只负责 HTTP 入口：
- 接收请求参数
- 调用 service 或 store
- 把数据库记录转换成 API 响应模型

路由层尽量不直接承载复杂业务规则，业务编排放在 service 层。
"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..core.schemas import (
    AgentEvent,
    AgentInput,
    AgentOutput,
    ResetInput,
    SessionDetail,
    SessionSummary,
    ToolResult,
    TraceResponse,
    TraceRunSummary,
)
from ..runtime.services import reset_session_service, run_agent_service
from ..storage.db import get_db
from ..storage.session_store import SqliteSessionStore

router = APIRouter()


@router.post("/run", response_model=AgentOutput)
def run_agent_api(agent_input: AgentInput, db: Session = Depends(get_db)) -> AgentOutput:
    """执行一次 agent run 并返回本次结果。

    `Depends(get_db)` 是 FastAPI 的依赖注入写法：
    框架会在调用路由前先执行 `get_db()`，把数据库会话对象传进来。
    """

    return run_agent_service(agent_input, db)


@router.post("/reset")
def reset_session(payload: ResetInput, db: Session = Depends(get_db)) -> dict[str, bool]:
    """清空某个 session 的持久化状态。"""

    return reset_session_service(payload, db)


@router.get("/sessions", response_model=list[SessionSummary])
def list_sessions_api(db: Session = Depends(get_db)) -> list[SessionSummary]:
    """返回所有 session 的摘要列表。

    这里故意只返回 summary，不把完整 state_json 暴露给前端。
    """

    store = SqliteSessionStore(db)
    records = store.list_sessions()
    return [
        SessionSummary(
            session_id=record.session_id,
            session_name=record.session_name,
            created_at=record.created_at,
            updated_at=record.updated_at,
            last_agent_name=record.last_agent_name,
            last_skill_name=record.last_skill_name,
            message_count=record.message_count,
            last_reply_preview=record.last_reply_preview,
        )
        for record in records
    ]


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def read_session_api(session_id: str, db: Session = Depends(get_db)) -> SessionDetail:
    """返回单个 session 的详情和完整状态。"""

    store = SqliteSessionStore(db)
    record = store.read_session_record(session_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    state = store.read_session_state(session_id)
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    return SessionDetail(
        session_id=record.session_id,
        session_name=record.session_name,
        created_at=record.created_at,
        updated_at=record.updated_at,
        last_agent_name=record.last_agent_name,
        last_reply_preview=record.last_reply_preview,
        last_skill_name=record.last_skill_name,
        message_count=record.message_count,
        state=state,
    )


@router.get("/sessions/{session_id}/trace", response_model=TraceResponse)
def read_session_trace_api(
    session_id: str,
    run_id: Optional[str] = None,
    db: Session = Depends(get_db),
) -> TraceResponse:
    """按 session 读取历史 trace。

    如果传了 `run_id`，只返回该次 run。
    否则返回该 session 下的全部 run，顺序由 store 层保证稳定。
    """

    store = SqliteSessionStore(db)
    run_records = store.list_run_records(session_id, run_id=run_id)

    if not run_records:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trace not found")

    runs = []
    for run_record in run_records:
        event_rows = store.list_run_events(run_record.run_id)
        events = []

        for row in event_rows:
            # 数据库里保存的是 JSON 字符串；API 返回时要还原成结构化对象。
            tool_result = ToolResult.model_validate(json.loads(row.tool_result_json)) if row.tool_result_json else None
            events.append(
                AgentEvent(
                    index=row.event_index,
                    type=row.type,
                    content=row.content,
                    tool_name=row.tool_name,
                    tool_call_id=row.tool_call_id,
                    tool_result=tool_result,
                )
            )

        runs.append(
            TraceRunSummary(
                run_id=run_record.run_id,
                session_id=run_record.session_id,
                agent_name=run_record.agent_name,
                skill_name=run_record.skill_name,
                user_input=run_record.user_input,
                reply=run_record.reply,
                event_count=run_record.event_count,
                created_at=run_record.created_at,
                finished_at=run_record.finished_at,
                events=events,
            )
        )

    return TraceResponse(session_id=session_id, runs=runs)
