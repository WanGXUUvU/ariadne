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
from sqlalchemy.orm import Session

from agent_prototype.infra.db.engine import get_db
from agent_prototype.security.approval.service import ApprovalService
from agent_prototype.execution.resume.resume_run_service import ResumeRunService

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("/{approval_id}")
def get_approval_api(approval_id: str, db: Session = Depends(get_db)):
    service = ApprovalService(db)
    record = service.get_approval(approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return record


@router.post("/{approval_id}/approve")
async def approve(approval_id: str, db: Session = Depends(get_db)):
    service = ApprovalService(db)
    record = service.approve(approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return StreamingResponse(
        ResumeRunService(db).resume_run(approval_id, rejected=False),
        media_type="text/event-stream",
    )


@router.post("/{approval_id}/reject")
async def reject(approval_id: str, db: Session = Depends(get_db)):
    service = ApprovalService(db)
    record = service.reject(approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return StreamingResponse(
        ResumeRunService(db).resume_run(approval_id, rejected=True),
        media_type="text/event-stream",
    )


@router.post("/{approval_id}/approve_all")
async def approve_all(approval_id: str, db: Session = Depends(get_db)):
    service = ApprovalService(db)
    record = service.approve_all(approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return StreamingResponse(
        ResumeRunService(db).resume_run(approval_id, rejected=False),
        media_type="text/event-stream",
    )