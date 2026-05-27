from fastapi import APIRouter, Depends, status  # 导入路由、依赖和状态码
from sqlalchemy.orm import Session  # 导入数据库会话
from fastapi.responses import StreamingResponse
from agent_prototype.api.dto.schemas import AgentInput, AgentOutput, ResetInput, FinalizeRunInput, RunDetailResponse, ToolCallSummary  # 导入请求响应模型
from agent_prototype.execution.persistence.run_service import RunService
from agent_prototype.execution.runtime.agent_executor import _global_futures  # 导入全新的 RunService
from agent_prototype.memory.session.service import SessionService  # 导入全新的 SessionService
from agent_prototype.infra.db.engine import get_db  # 导入数据库依赖
from agent_prototype.api.routes.dependencies import error_response  # 导入统一错误响应

router = APIRouter()  # 创建本文件路由器


@router.post("/run", response_model=AgentOutput)  # 定义 /run 接口
def run_agent_api(agent_input: AgentInput, db: Session = Depends(get_db)) -> AgentOutput:  # 接收输入和 DB
    """输入：AgentInput 和数据库会话。输出：AgentOutput。"""  # 接口说明
    try:  # 捕获业务错误
        service = RunService(db)
        return service.run_agent(agent_input)  # 实例化并调用 OOP 成员方法
    except ValueError as exc:  # 捕获参数或业务校验错误
        return error_response(status.HTTP_400_BAD_REQUEST, "bad_request", str(exc))  # 返回统一错误


@router.post("/reset")  # 定义 /reset 接口
def reset_session_api(payload: ResetInput, db: Session = Depends(get_db)) -> dict[str, bool]:  # 接收重置请求
    """输入：ResetInput 和数据库会话。输出：是否重置成功。"""  # 接口说明
    try:  # 捕获业务错误
        service = SessionService(db)
        return service.reset_session(payload)  # 实例化并调用 SessionService 成员方法
    except ValueError as exc:  # 捕获业务错误
        return error_response(status.HTTP_400_BAD_REQUEST, "bad_request", str(exc))  # 返回统一错误


@router.post("/run/stream")
async def run_stream_api(agent_input: AgentInput, db: Session = Depends(get_db)) -> StreamingResponse:
    """输入：AgentInput 和数据库会话。输出：SSE 流式响应。"""
    try:
        service = RunService(db)
        return StreamingResponse(
            service.async_stream_agent(agent_input),
            media_type="text/event-stream",
        )
    except ValueError as exc:
        return error_response(status.HTTP_400_BAD_REQUEST, "bad request", str(exc))


@router.post("/sessions/{session_id}/runs/{run_id}/finalize")
def finalize_run_api(session_id: str, run_id: str, payload: FinalizeRunInput, db: Session = Depends(get_db)):
    try:
        service = RunService(db)
        return service.finalize_run(
            session_id=session_id,
            run_id=run_id,
            user_input=payload.user_input,
            partial_reply=payload.partial_reply,
            agent_name=payload.agent_name,
            skill_name=payload.skill_name,
        )
    except ValueError as exc:
        return error_response(status.HTTP_400_BAD_REQUEST, "bad_request", str(exc))


@router.get("/sessions/{session_id}/runs/{run_id}")
def get_run_detail_api(session_id: str, run_id: str, db: Session = Depends(get_db)):
    service = RunService(db)
    run, tool_calls = service.get_run_detail(session_id, run_id)
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


@router.get("/child-runs/{run_id}")
def get_child_run_status_api(run_id: str):
    """输入：child_run_id。输出：子 Agent 状态（running/done/error）和结果。纯内存，重启后消失。"""
    future = _global_futures.get(run_id)
    if future is None:
        return {"status": "not_found", "reply": None, "error": None}
    if not future.done():
        return {"status": "running", "reply": None, "error": None}
    exc = future.exception()
    if exc:
        return {"status": "error", "reply": None, "error": str(exc)}
    result = future.result()
    del _global_futures[run_id]
    return {"status": "done", "reply": result.reply, "error": None}