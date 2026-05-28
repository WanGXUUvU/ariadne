"""接口与适配层 (Interface Layer) - 执行路由控制器

职责：
1. 提供执行流（Run）相关 API 路由控制（/run, /run/stream, /run/{run_id}/resume）。
2. 处理 SSE/HTTP 流式响应及打字机效果数据封装。
3. 使用 Pydantic 进行输入参数强校验（如 RunInput DTO）。

不负责：
1. 具体的 Agent 执行流控制（由 Application Runtime 层负责）。
2. 数据持久化存取细节（由 PersistService 负责）。

数据流向：
- 输入：HTTP POST / GET / SSE 请求及输入校验 DTO。
- 输出：HTTP JSON 响应或 SSE 事件流。
- 上游来源：前端对话视窗 / 审批卡片。
- 下游流向：调用 agent_prototype/execution/service.py 进行业务编排。
"""

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from agent_prototype.core.types import AgentInput, AgentOutput, FinalizeRunInput, ResetInput
from agent_prototype.api.dto.schemas import RunDetailResponse, ToolCallSummary
from agent_prototype.execution.service import RunService
from agent_prototype.execution.runtime.agent_executor import _global_futures
from agent_prototype.memory.session.service import SessionService
from agent_prototype.api.routes.dependencies import (
    error_response,
    get_run_service,
    get_session_service,
)

router = APIRouter()  # 创建本文件路由器


@router.post("/run", response_model=AgentOutput)
def run_agent_api(agent_input: AgentInput, service: RunService = Depends(get_run_service)) -> AgentOutput:
    """这个函数是用来让指定的 Agent 跑起来并立刻给出完整答复的（非流式）。
    
    就像发微信消息一样，你发一句话，它在后台默默思考、查工具，等全部想好之后一次性把完整答案回给你。
    
    需要拿到的东西：
    - agent_input: AgentInput 对象，里面包含当前在哪个会话聊天、用户发了什么、用哪个 Agent 模板等。
    - service: RunService 实例，由依赖注入提供。
    
    会给出来的结果：
    - AgentOutput 对象，里面包含了 Agent 的回答以及这次运行的一些状态信息。
    """
    try:
        return service.run_agent(agent_input)
    except ValueError as exc:
        return error_response(status.HTTP_400_BAD_REQUEST, "bad_request", str(exc))


@router.post("/reset")
def reset_session_api(payload: ResetInput, service: SessionService = Depends(get_session_service)) -> dict[str, bool]:
    """这个函数是用来彻底重置或者清空某个聊天会话的历史记录的。
    
    就像你跟客服聊天按了“清除历史记录”或者“重新开始”一样，清空后可以重新开始一段干净的对话。
    
    需要拿到的东西：
    - payload: ResetInput 对象，里面需要包含你要重置哪一个会话（session_id）。
    - service: SessionService 实例，由依赖注入提供。
    
    会给出来的结果：
    - 一个字典，形如 {"status": True}，告诉你重置操作是否成功了。
    """
    try:
        return service.reset_session(payload)
    except ValueError as exc:
        return error_response(status.HTTP_400_BAD_REQUEST, "bad_request", str(exc))


@router.post("/run/stream")
async def run_stream_api(agent_input: AgentInput, service: RunService = Depends(get_run_service)) -> StreamingResponse:
    """这个函数是用来让指定的 Agent 跑起来并像“打字机”一样源源不断地实时流式返回它的思考和回答的（SSE 协议）。
    
    当你要做聊天界面，希望用户能实时看到 Agent 正在一个字一个字蹦出来答案时，就用这个接口。
    
    需要拿到的东西：
    - agent_input: AgentInput 对象，包含了会话、用户输入和 Agent 配置。
    - service: RunService 实例，由依赖注入提供。
    
    会给出来的结果：
    - 一个 StreamingResponse 流式响应，浏览器可以通过 EventSource 监听并实时渲染 Agent 的打字效果。
    """
    try:
        return StreamingResponse(
            service.async_stream_agent(agent_input),
            media_type="text/event-stream",
        )
    except ValueError as exc:
        return error_response(status.HTTP_400_BAD_REQUEST, "bad request", str(exc))


@router.post("/sessions/{session_id}/runs/{run_id}/finalize")
def finalize_run_api(session_id: str, run_id: str, payload: FinalizeRunInput, service: RunService = Depends(get_run_service)):
    """这个函数是用来手动终结或归档一次 Agent 运行记录的。
    
    当一次运行由于异常、用户打断或某些外部原因没有正常结束，或者需要人工把回复内容强行写进历史记录时，可以用这个接口来强行写个结尾。
    
    需要拿到的东西：
    - session_id: 字符串类型，当前会话的唯一标识。
    - run_id: 字符串类型，当前运行实例的唯一标识.
    - payload: FinalizeRunInput 对象，包含强行写入的用户输入、部分回复、Agent 名字和 Skill 名字等信息。
    - service: RunService 实例，由依赖注入提供。
    
    会给出来的结果：
    - 归档操作完成后的运行记录结果。
    """
    try:
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
def get_run_detail_api(session_id: str, run_id: str, service: RunService = Depends(get_run_service)):
    """这个函数是用来获取某次 Agent 运行的超详细内幕信息的。
    
    比如这次运行中，Agent 到底调用了哪些工具？工具是什么时候开始调用的，什么时候结束的，工具的输入参数是什么，吐出来的结果是什么，都会被一览无余地查出来。
    
    需要拿到的东西：
    - session_id: 字符串类型，会话 ID。
    - run_id: 字符串类型，运行记录 ID。
    - service: RunService 实例，由依赖注入提供。
    
    会给出来的结果：
    - RunDetailResponse 对象，里面有运行状态、用户输入、最终回复，以及详细的 tool_calls 工具调用记录列表。
    """
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
    """这个函数是用来查询异步启动的子 Agent（Child Run）当前运行到哪了。
    
    因为子 Agent 是丢到后台默默跑的，我们需要拿着它的 ID 去前台“轮询”查查它跑完没有、报错了没有，还是正在跑。
    
    需要拿到的东西：
    - run_id: 字符串类型，子 Agent 运行的唯一身份证。
    
    会给出来的结果：
    - 一个字典，告诉你当前状态（例如 "running", "done", "error", "not_found"），如果是 done 还会附带上回复内容 reply，如果是 error 则会附带报错信息 error。
    """
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