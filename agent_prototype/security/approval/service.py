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

    这个类是“审批业务大管家”。
    它主要负责在业务层打理一切审批工作。比如：帮别人去查一张审批工单的详情；当人类点击了“同意”按钮时，它来批准这笔工单；点击“拒绝”时，它来驳回工单；或者点击“全自动执行（approve_all）”时，它不仅同意当前这笔，还会顺便把当前会话的权限级别直接连升三级变成“full-auto 全自动运行状态”，并且负责保存并提交数据库事务。
    """

    def __init__(self, db: Session):
        """审批服务大管家初始化，带上数据库的“钥匙”，并且叫上底下的工单仓库管理员。

        需要拿到的东西：
        - db (Session): 数据库会话连接。
        """
        self.db = db
        self.store = SqliteApprovalStore(db)

    def get_approval(self, approval_id: str) -> Optional[PendingApproval]:
        """根据审批单号查出工单的全部内容。

        需要拿到的东西：
        - approval_id (str): 审批单的 ID 编号。

        会给出来的结果：
        - Optional[PendingApproval]: 查出来的数据库审批记录详情，找不到就返回 None。
        """
        return self.store.get(approval_id)

    def approve(self, approval_id: str) -> Optional[PendingApproval]:
        """批准这笔审批工单。把工单状态改成“approved（已批准）”并马上保存提交到数据库。

        需要拿到的东西：
        - approval_id (str): 审批单的 ID 编号。

        会给出来的结果：
        - Optional[PendingApproval]: 批准成功后的审批记录详情，如果压根没查到这笔单子就返回 None。
        """
        record = self.store.update_status(approval_id, "approved")
        if record is None:
            return None
        self.db.commit()
        return record

    def reject(self, approval_id: str) -> Optional[PendingApproval]:
        """驳回这笔审批工单。把工单状态改成“rejected（已拒绝）”并马上保存提交到数据库。

        需要拿到的东西：
        - approval_id (str): 审批单的 ID 编号。

        会给出来的结果：
        - Optional[PendingApproval]: 驳回成功后的审批记录详情，如果压根没查到这笔单子就返回 None。
        """
        record = self.store.update_status(approval_id, "rejected")
        if record is None:
            return None
        self.db.commit()
        return record

    def approve_all(self, approval_id: str) -> Optional[PendingApproval]:
        """超级批准工单。
        不仅把当前这笔敏感工具调用的工单批准通过，还会大笔一挥，直接把这个会话的安全权限配置修改成“full-auto（全自动无需人工审批模式）”，表示后面遇到再多危险工具也不用拦截了。然后立即存入数据库并提交事务。

        需要拿到的东西：
        - approval_id (str): 审批单的 ID 编号。

        会给出来的结果：
        - Optional[PendingApproval]: 批准成功后的审批记录详情，如果找不到就返回 None。
        """

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
