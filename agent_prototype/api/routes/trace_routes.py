"""接口与适配层 (Interface Layer) - 轨迹路由控制器

职责：
1. 提供执行细节（Trace/Events）的 HTTP 查询路由控制器。
2. 允许按 Run ID 查询所有细粒度事件以供前端渲染。

不负责：
1. 运行中 Trace 事件的实时拦截与收集。
2. 日志的物理落盘与监控。

数据流向：
- 输入：HTTP GET 请求及会话/Run 查询入参。
- 输出：Trace 细粒度事件列表 JSON 响应。
- 上游来源：前端 Trace 侧边栏及手风琴卡片。
- 下游流向：调用 agent_prototype/memory/session/service.py。
"""

from typing import Optional
from fastapi import APIRouter, Depends, status
from agent_prototype.api.dto.schemas import TraceResponse, TraceRunSummary
from agent_prototype.execution.service import RunService
from agent_prototype.api.routes.dependencies import error_response, get_run_service

router = APIRouter()  # 创建路由器

@router.get("/sessions/{session_id}/trace", response_model=TraceResponse)
def read_session_trace_api(session_id: str, run_id: Optional[str] = None, service: RunService = Depends(get_run_service)) -> TraceResponse:
    """这个函数是用来读取会话在后台运行时的详细执行轨迹（Trace/运行步骤）的。
    
    它可以帮你还原 Agent 思考的每一步：到底是在脑子里想（Thinking），还是在调用工具（Tool Calling），又或者是出错了（Error），方便你调试和追踪。
    
    需要拿到的东西：
    - session_id: 字符串类型，当前会话的唯一身份证。
    - run_id: 可选的字符串，如果传了就只查某一次运行的具体轨迹；如果不传，就会列出这个会话下所有的运行轨迹。
    - service: RunService 实例，由依赖注入提供。
    
    会给出来的结果：
    - TraceResponse 对象，里面不仅包含了运行概况（比如输入、最终回复、耗时等），还包含了最核心的事件步骤列表 events，还原 Agent 思考的完整链路。
    """
    run_records, events_map = service.get_session_trace(session_id, run_id=run_id)
    if not run_records:
        return error_response(status.HTTP_404_NOT_FOUND, "trace_not_found", "Trace not found")

    runs = []
    for run_record in run_records:
        events = events_map.get(run_record.run_id, [])
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
