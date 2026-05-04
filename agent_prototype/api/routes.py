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
    SkillSummary,
)
from ..runtime.services import reset_session_service, run_agent_service
from ..storage.db import get_db
from ..storage.session_store import SqliteSessionStore
from ..runtime.skill_loader import list_skills
from ..runtime.skill_service import disable_skill_service,enable_skill_service
router = APIRouter()


@router.post("/run", response_model=AgentOutput)
def run_agent_api(agent_input: AgentInput, db: Session = Depends(get_db)) -> AgentOutput:
    """输入：AgentInput 请求对象、数据库会话。输出：AgentOutput 响应对象。"""

    try:
        return run_agent_service(agent_input, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))



@router.post("/reset")
def reset_session(payload: ResetInput, db: Session = Depends(get_db)) -> dict[str, bool]:
    """输入：ResetInput 请求对象、数据库会话。输出：是否重置成功的结果字典。"""

    return reset_session_service(payload, db)


@router.get("/sessions", response_model=list[SessionSummary])
def list_sessions_api(db: Session = Depends(get_db)) -> list[SessionSummary]:
    """输入：数据库会话。输出：SessionSummary 列表。

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
    """输入：session_id、数据库会话。输出：单个 session 的详情对象。"""

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
    """输入：session_id、可选 run_id、数据库会话。输出：TraceResponse 回放结果。

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

@router.get("/skills",response_model=list[SkillSummary])
def list_skills_api()->list[SkillSummary]:
    """输入：无。输出：当前可见的 SkillSummary 列表。"""

    return list_skills()

@router.post("/skills/{skill_name}/disable",response_model=SkillSummary)
def disable_skill_api(skill_name:str)->SkillSummary:
    """输入skill name 输出 金庸后的SkillSummary"""
    try:
        return disable_skill_service(skill_name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail=str(exc))

@router.post("/skills/{skill_name}/enable", response_model=SkillSummary)
def enable_skill_api(skill_name: str) -> SkillSummary:
    """输入：skill 名称。输出：启用后的 SkillSummary。"""
    try:
        return enable_skill_service(skill_name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
