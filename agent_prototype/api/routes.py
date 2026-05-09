"""FastAPI 路由层。

这个文件只负责 HTTP 入口：
- 接收请求参数
- 调用 service 或 store
- 把数据库记录转换成 API 响应模型

路由层尽量不直接承载复杂业务规则，业务编排放在 service 层。
"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse

from ..core.schemas import (
    AgentEvent,
    AgentInput,
    AgentOutput,
    ApiError,
    CompactInput,
    CompactOutput,
    CreateSessionInput,
    ErrorResponse,
    ResetInput,
    SessionDetail,
    SessionSummary,
    ToolResult,
    TraceResponse,
    TraceRunSummary,
    SkillSummary,
)
from ..runtime.services import reset_session_service, run_agent_service,compact_session_service,create_session_service,delete_session_service
from ..storage.db import get_db
from ..storage.session_store import SqliteSessionStore
from ..runtime.skill_loader import list_skills
from ..runtime.skill_service import disable_skill_service,enable_skill_service
router = APIRouter()

def error_response(status_code:int,code:str,message:str)->JSONResponse:
    """输入：HTTP状态码、错误代码、错误文案。输出：统一错误响应格式"""
    
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            error=ApiError(
                code=code,
                message=message,
            )
        ).model_dump()
    )

@router.post("/run", response_model=AgentOutput)
def run_agent_api(agent_input: AgentInput, db: Session = Depends(get_db)) -> AgentOutput:
    """输入：AgentInput 请求对象、数据库会话。输出：AgentOutput 响应对象。"""  # /run 正常成功时仍然返回 AgentOutput

    try:
        return run_agent_service(agent_input, db)  # 正常路径仍然直接复用 service 层结果
    except ValueError as exc:
        return error_response(  # 统一返回顶层 error，不再抛 HTTPException(detail=...)
            status.HTTP_400_BAD_REQUEST,  # 这类错误仍然是 400
            "bad_request",  # 第一版先统一用 bad_request，后面再细分
            str(exc),  # 直接沿用当前业务错误文本
        )




@router.post("/reset")
def reset_session(payload: ResetInput, db: Session = Depends(get_db)) -> dict[str, bool]:
    """输入：ResetInput 请求对象、数据库会话。输出：是否重置成功的结果字典。"""
    try:
        return reset_session_service(payload, db)
    except ValueError as exc:
        return error_response(
            status.HTTP_400_BAD_REQUEST,
            "bad_request",
            str(exc),
        )

@router.post("/sessions", response_model=SessionSummary)
def create_session_api(payload: CreateSessionInput, db: Session = Depends(get_db)) -> SessionSummary:
    """输入：CreateSessionInput 请求对象、数据库会话。输出：新建 session 的摘要信息。"""  # 这个接口只负责创建空白 session，不负责发第一条消息

    return create_session_service(payload, db)  # 直接把请求交给 service 层，保持 route 层只做 HTTP 适配

@router.delete("/sessions/{session_id}")  # 删除某一条 session，路径要和现有 /sessions 体系保持一致
def delete_session_api(session_id:str,db:Session=Depends(get_db)):
    """输入：session_id、数据库会话。输出：是否删除成功的结果字典。"""  # route 层只负责接 HTTP 请求并转交给 service

    try:
        return delete_session_service(session_id,db)
    except ValueError as exc:
        return error_response(
            status.HTTP_400_BAD_REQUEST,
            "bad_request",
            str(exc),
        )

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
        return error_response(  # session 记录不存在时返回统一 404 错误结构
            status.HTTP_404_NOT_FOUND,  # HTTP 状态码保持 404
            "session_not_found",  # 给前端稳定错误代码
            "Session not found",  # 给人看的错误文案
        )

    state = store.read_session_state(session_id)
    if state is None:
        return error_response(  # state 丢失时也统一成同一个错误结构
            status.HTTP_404_NOT_FOUND,  # 仍然返回 404
            "session_not_found",  # 第一版先和上面共用同一错误码
            "Session not found",  # 保持相同文案，避免前端处理分叉
        )
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
        return error_response(  # trace 查不到时也走统一错误响应
            status.HTTP_404_NOT_FOUND,  # 资源不存在，返回 404
            "trace_not_found",  # 给 trace 场景单独的机器可读错误码
            "Trace not found",  # 给用户/CLI 的可读提示
        )

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
        return error_response(  # skill 业务错误统一成结构化响应
            status.HTTP_400_BAD_REQUEST,  # 非法 skill 请求仍然是 400
            "bad_request",  # 第一版先统一错误码
            str(exc),  # 保留当前 service 抛出的具体原因
        )

@router.post("/skills/{skill_name}/enable", response_model=SkillSummary)
def enable_skill_api(skill_name: str) -> SkillSummary:
    """输入：skill 名称。输出：启用后的 SkillSummary。"""
    try:
        return enable_skill_service(skill_name)
    except ValueError as exc:
        return error_response(  # skill 业务错误统一成结构化响应
            status.HTTP_400_BAD_REQUEST,  # 非法 skill 请求仍然是 400
            "bad_request",  # 第一版先统一错误码
            str(exc),  # 保留当前 service 抛出的具体原因
        )
    
@router.post("/compact",response_model=CompactOutput)
def compact_session_api(payload:CompactInput,db:Session=Depends(get_db))->CompactOutput:
    """输入：CompactInput 请求对象、数据库会话。输出：CompactOutput 响应对象。"""  # 暴露手动 compact 的 HTTP 入口
    
    try:
        return compact_session_service(payload,db)
    except ValueError as exc:
        return error_response(  # compact 的业务错误也统一走同一套格式
            status.HTTP_400_BAD_REQUEST,  # 当前 compact 失败仍按 400 处理
            "bad_request",  # 第一版保持简单统一
            str(exc),  # 直接带出 service 的错误信息
        )
