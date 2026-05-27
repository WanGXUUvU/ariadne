"""应用服务层 (Application Layer) - 人工审批管理服务

职责：
1. 编排工具调用审批（Approval）的状态更新（通过 / 拒绝 / 提升权限为 full-auto）。
2. 控制事务提交，保证审批状态在数据库持久化中的一致性。

不负责：
1. 具体的中间件拦截逻辑（由 ApprovalGateInterceptor 在 runtime 中间件层负责）。
2. 网络接口控制器路由的暴露。

数据流向：
- 输入：审批工单 ID（approval_id）及决策状态。
- 输出：状态更新后的 PendingApproval 实体。
- 上游来源：agent_prototype/api/routes/approval_routes.py。
- 下游流向：调用 agent_prototype/security/approval/store.py 写入数据库。
"""

# ── 第三方库 ──────────────────────────────────────────────────────────────────
from typing import Optional

from sqlalchemy.orm import Session

# ── 本地模块 ──────────────────────────────────────────────────────────────────
from agent_prototype.infra.db.orm_models import PendingApproval, SessionRecord
from agent_prototype.security.approval.store import SqliteApprovalStore


class ApprovalService:
    """工具调用审批管理服务类
    
    职责：
    1. 管理挂起审批记录的状态改变；
    2. 控制事务的提交与一致性。
    """
    
    def __init__(self, db: Session):
        """注入 db 会话，聚合仓储"""
        self.db = db
        self.store = SqliteApprovalStore(db)

    def get_approval(self, approval_id: str) -> Optional[PendingApproval]:
        """输入：approval_id。输出：审批记录实体"""
        return self.store.get(approval_id)

    def approve(self, approval_id: str) -> Optional[PendingApproval]:
        """输入：approval_id。输出：更新为 approved 状态的记录"""
        record = self.store.update_status(approval_id, "approved")
        if record is None:
            return None
        self.db.commit()
        return record

    def reject(self, approval_id: str) -> Optional[PendingApproval]:
        """输入：approval_id。输出：更新为 rejected 状态的记录"""
        record = self.store.update_status(approval_id, "rejected")
        if record is None:
            return None
        self.db.commit()
        return record

    def approve_all(self, approval_id: str) -> Optional[PendingApproval]:
        """审批通过，并将所在 session 的权限档位提升为 full-auto。

        :param approval_id: 待审批的记录 ID
        :return: 更新为 approved 状态的记录，未找到时返回 None
        """
        from agent_prototype.infra.db.orm_models import SessionRecord

        record = self.store.update_status(approval_id, "approved")
        if record is None:
            return None
        session_record = (
            self.db.query(SessionRecord)
            .filter(SessionRecord.session_id == record.session_id)
            .first()
        )
        if session_record:
            session_record.permission_profile = "full-auto"
        self.db.commit()
        return record