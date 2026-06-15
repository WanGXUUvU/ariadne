"""接口与适配层 (Interface Layer) - 审批路由控制器

职责：
1. 提供人工审批决策的 HTTP 处理路由。
2. 支持查询审批工单状态、提交审批决定（同意/拒绝/修改参数）。

不负责：
1. 审批工单的底层物理存储与持久化操作。
2. 运行时中间件的暂停与唤醒信号管理。

数据流向：
- 输入：HTTP POST /api/v1/approvals DTO。
- 输出：审批提交状态 JSON 响应。
- 上游来源：前端审批卡片交互。
- 下游流向：调用 agent_prototype/security/approval/service.py 执行审批逻辑。
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from agent_prototype.security.approval.service import ApprovalRunNotPaused, ApprovalService
from agent_prototype.execution.resume.service import ResumeRunService
from agent_prototype.api.routes.dependencies import (
    get_approval_service,
    get_resume_run_service,
)

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("/{approval_id}")
def get_approval_api(approval_id: str, service: ApprovalService = Depends(get_approval_service)):
    """这个函数是用来查询单条审批工单信息的。

    如果 Agent 在执行某个敏感工具前被暂停了需要人去确认，你就可以用这个接口把它的状态和详细审批请求查出来。

    需要拿到的东西：
    - approval_id: 字符串类型，代表这条审批记录的唯一身份证。
    - service: ApprovalService 实例，由依赖注入提供。

    会给出来的结果：
    - 审批记录的详细信息。如果没找到，会抛出 404 错误（表示找不到这个审批）。
    """
    record = service.get_approval(approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return record


@router.post("/{approval_id}/approve")
async def approve(
    approval_id: str,
    service: ApprovalService = Depends(get_approval_service),
    resume_service: ResumeRunService = Depends(get_resume_run_service),
):
    """这个函数是用来同意某一次工具执行审批的。

    当你点击了“同意”，系统会标记这条审批为已同意，并且把暂停的 Agent 重新叫醒，让它继续往下跑。

    需要拿到的东西：
    - approval_id: 字符串类型，代表这条审批记录的唯一身份证。
    - service: ApprovalService 实例，由依赖注入提供。
    - resume_service: ResumeRunService 实例，由依赖注入提供。

    会给出来的结果：
    - 一个 StreamingResponse 流式响应，里面源源不断地吐出 Agent 被唤醒后继续执行的日志/事件流。
    """
    try:
        record = service.approve(approval_id)
    except ApprovalRunNotPaused as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return StreamingResponse(
        resume_service.resume_run(approval_id, rejected=False),
        media_type="text/event-stream",
    )


@router.post("/{approval_id}/reject")
async def reject(
    approval_id: str,
    service: ApprovalService = Depends(get_approval_service),
    resume_service: ResumeRunService = Depends(get_resume_run_service),
):
    """这个函数是用来拒绝某一次工具执行审批的。

    当你点击了“拒绝”，系统会标记这条审批为已拒绝，并且会通知 Agent 这次执行被拒绝了，让 Agent 继续以被拒后的状态运行或报错。

    需要拿到的东西：
    - approval_id: 字符串类型，代表这条审批记录的唯一身份证。
    - service: ApprovalService 实例，由依赖注入提供。
    - resume_service: ResumeRunService 实例，由依赖注入提供。

    会给出来的结果：
    - 一个 StreamingResponse 流式响应，里面源源不断地吐出 Agent 被拒绝后继续处理或报错的日志/事件流。
    """
    try:
        record = service.reject(approval_id)
    except ApprovalRunNotPaused as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return StreamingResponse(
        resume_service.resume_run(approval_id, rejected=True),
        media_type="text/event-stream",
    )


@router.post("/{approval_id}/approve_all")
async def approve_all(
    approval_id: str,
    service: ApprovalService = Depends(get_approval_service),
    resume_service: ResumeRunService = Depends(get_resume_run_service),
):
    """这个函数是用来一键同意后面所有需要审批的步骤的（比如免密/信任模式）。

    执行之后，系统会同意当前的审批，并把 Agent 叫醒。

    需要拿到的东西：
    - approval_id: 字符串类型，代表这条审批记录的唯一身份证。
    - service: ApprovalService 实例，由依赖注入提供。
    - resume_service: ResumeRunService 实例，由依赖注入提供。

    会给出来的结果：
    - 一个 StreamingResponse 流式响应，里面源源不断地吐出 Agent 被唤醒后继续执行的日志/事件流。
    """
    try:
        record = service.approve_all(approval_id)
    except ApprovalRunNotPaused as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return StreamingResponse(
        resume_service.resume_run(approval_id, rejected=False),
        media_type="text/event-stream",
    )
