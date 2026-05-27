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

import json  # 解析 JSON 字符串
from typing import Optional  # 可选参数
from fastapi import APIRouter, Depends, status  # 导入路由、依赖和状态码
from sqlalchemy.orm import Session  # 导入数据库会话
from agent_prototype.api.dto.schemas import AgentEvent, ToolResult, TraceResponse, TraceRunSummary  # 导入 schema
from agent_prototype.infra.db.engine import get_db  # 导入数据库依赖
from agent_prototype.memory.session.store import SqliteSessionStore  # 导入 session store
from agent_prototype.api.routes.dependencies import error_response  # 导入统一错误响应

router = APIRouter()  # 创建路由器

@router.get("/sessions/{session_id}/trace", response_model=TraceResponse)  # 定义 trace 接口
def read_session_trace_api(session_id: str, run_id: Optional[str] = None, db: Session = Depends(get_db)) -> TraceResponse:  # 接收参数
    """输入：session_id、可选 run_id、数据库会话。输出：TraceResponse。"""  # 接口说明
    store = SqliteSessionStore(db)  # 创建 store
    run_records = store.list_run_records(session_id, run_id=run_id)  # 读取 run 记录
    if not run_records:  # 没有 trace
        return error_response(status.HTTP_404_NOT_FOUND, "trace_not_found", "Trace not found")  # 返回 404
    runs = []  # 准备返回结果
    for run_record in run_records:  # 遍历 run
        event_rows = store.list_run_events(run_record.run_id)  # 读取事件行
        events = []  # 准备事件列表
        for row in event_rows:  # 遍历事件
            tool_result = ToolResult.model_validate(json.loads(row.tool_result_json)) if row.tool_result_json else None  # 反序列化 tool result
            events.append(  # 追加事件
                AgentEvent(  # 构造事件对象
                    index=row.event_index,  # 事件序号
                    type=row.type,  # 事件类型
                    content=row.content,  # 事件内容
                    tool_name=row.tool_name,  # tool 名称
                    tool_call_id=row.tool_call_id,  # tool call id
                    tool_result=tool_result,  # tool result
                )  # 事件对象结束
            )  # 追加结束
        runs.append(  # 追加 run 概要
            TraceRunSummary(  # 构造 run 概要
                run_id=run_record.run_id,  # run id
                session_id=run_record.session_id,  # session id
                agent_name=run_record.agent_name,  # agent 名
                skill_name=run_record.skill_name,  # skill 名
                user_input=run_record.user_input,  # 用户输入
                reply=run_record.reply,  # 回复
                event_count=run_record.event_count,  # 事件数
                created_at=run_record.created_at,  # 创建时间
                finished_at=run_record.finished_at,  # 结束时间
                events=events,  # 事件列表
            )  # run 概要结束
        )  # run 追加结束
    return TraceResponse(session_id=session_id, runs=runs)  # 返回 trace 响应
