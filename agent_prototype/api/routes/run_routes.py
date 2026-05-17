from fastapi import APIRouter, Depends, status  # 导入路由、依赖和状态码
from sqlalchemy.orm import Session  # 导入数据库会话
from fastapi.responses import StreamingResponse
from ...core.schemas import AgentInput, AgentOutput, CompactInput, CompactOutput, ResetInput,FinalizeRunInput,RunDetailResponse,ToolCallSummary  # 导入请求响应模型
from ...application.run_service import run_agent_service,async_stream_agent_service,finalize_run_service,get_run_detail_service # /run 主链路服务
from ...application.compact_service import compact_session_service  # /compact 独立服务
from ...application.session_service import reset_session_service  # /reset 独立服务
from ...storage.db import get_db  # 导入数据库依赖
from .common import error_response  # 导入统一错误响应

router = APIRouter()  # 创建本文件路由器

@router.post("/run", response_model=AgentOutput)  # 定义 /run 接口
def run_agent_api(agent_input: AgentInput, db: Session = Depends(get_db)) -> AgentOutput:  # 接收输入和 DB
    """输入：AgentInput 和数据库会话。输出：AgentOutput。"""  # 接口说明
    try:  # 捕获业务错误
        return run_agent_service(agent_input, db)  # 交给 service 处理
    except ValueError as exc:  # 捕获参数或业务校验错误
        return error_response(status.HTTP_400_BAD_REQUEST, "bad_request", str(exc))  # 返回统一错误

@router.post("/reset")  # 定义 /reset 接口
def reset_session_api(payload: ResetInput, db: Session = Depends(get_db)) -> dict[str, bool]:  # 接收重置请求
    """输入：ResetInput 和数据库会话。输出：是否重置成功。"""  # 接口说明
    try:  # 捕获业务错误
        return reset_session_service(payload, db)  # 交给 service 处理
    except ValueError as exc:  # 捕获业务错误
        return error_response(status.HTTP_400_BAD_REQUEST, "bad_request", str(exc))  # 返回统一错误

@router.post("/compact", response_model=CompactOutput)  # 定义 /compact 接口
def compact_session_api(payload: CompactInput, db: Session = Depends(get_db)) -> CompactOutput:  # 接收 compact 请求
    """输入：CompactInput 和数据库会话。输出：CompactOutput。"""  # 接口说明
    try:  # 捕获业务错误
        return compact_session_service(payload, db)  # 交给 service 处理
    except ValueError as exc:  # 捕获业务错误
        return error_response(status.HTTP_400_BAD_REQUEST, "bad_request", str(exc))  # 返回统一错误

@router.post("/run/stream")
async def run_stream_api(agent_input:AgentInput,db:Session=Depends(get_db))->StreamingResponse:
    """输入：AgentInput 和数据库会话。输出：SSE 流式响应。"""

    try:
        return StreamingResponse(async_stream_agent_service(agent_input,db),media_type="text/event-stream",)
    except ValueError as exc:
        return error_response(status.HTTP_400_BAD_REQUEST,"bad request",str(exc))
    
@router.post("/sessions/{session_id}/runs/{run_id}/finalize")
def finalize_run_api(session_id: str, run_id: str, payload: FinalizeRunInput, db: Session = Depends(get_db)):
    try:
        return finalize_run_service(session_id, run_id, payload.user_input, payload.partial_reply, payload.agent_name, payload.skill_name, db)
    except ValueError as exc:
        return error_response(status.HTTP_400_BAD_REQUEST, "bad_request", str(exc))
    

@router.get("/sessions/{session_id}/runs/{run_id}")
def get_run_detail_api(session_id: str, run_id: str, db: Session = Depends(get_db)):
    run, tool_calls = get_run_detail_service(session_id, run_id, db)
    if not run:
        return error_response(status.HTTP_404_NOT_FOUND, "not found", "run not found")
    return RunDetailResponse(
        run_id=run.run_id,
        session_id=run.session_id,
        run_status=run.run_status,
        user_input=run.user_input,
        reply=run.reply,
        agent_name=run.agent_name,
        skill_name=run.skill_name,
        created_at=run.created_at,
        tool_calls=[
            ToolCallSummary(
                id=tc.id,
                tool_name=tc.tool_name,
                tool_call_id=tc.tool_call_id,
                status=tc.status,
                input_json=tc.input_json,
                result_json=tc.result_json,
                started_at=tc.started_at,
                finished_at=tc.finished_at,
            )
            for tc in tool_calls
        ],
    )