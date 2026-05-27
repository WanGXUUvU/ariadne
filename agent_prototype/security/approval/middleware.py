"""人工审批拦截中间件。

职责：
1. 仅在需要时（如 standard 档位下的 DANGER 工具）拦截工具；
2. 触发外部观察者回调进行 pending_approvals 的持久化，并抛出控制流中断异常。
"""

import logging
from typing import Awaitable, Callable

from agent_prototype.model.types.domain import ToolResult, ApprovalPolicy, needs_approval
from agent_prototype.security.middleware.base import BaseMiddleware
from agent_prototype.security.middleware.base import ToolCallContext

logger = logging.getLogger(__name__)


class ApprovalRequiredException(Exception):
    """当工具调用需要审批拦截时抛出的特定控制流中断异常。"""

    def __init__(self, approval_id: str):
        self.approval_id = approval_id
        super().__init__(f"Approval required: {approval_id}")


class ApprovalMiddleware(BaseMiddleware):
    """人工审批中间件。"""

    async def call(
        self,
        context: ToolCallContext,
        next_call: Callable[[], Awaitable[ToolResult]],
    ) -> ToolResult:
        logger.info(f"[ApprovalMiddleware] 正在校验工具 {context.tool_name} 是否需要触发审批...")
        
        # 1. 从小推车上下文读取元数据
        approval_policy = context.extra.get("approval_policy", ApprovalPolicy.NEVER)
        risk_level      = context.extra.get("risk_level")
        on_approval_required = context.extra.get("on_approval_required")
        
        # 2. 判断是否触发拦截
        if risk_level is not None and needs_approval(approval_policy, risk_level):
            logger.warning(f"[ApprovalMiddleware] 工具 {context.tool_name} 触发审批拦截策略: {approval_policy}")
            approval_id = None
            
            if on_approval_required:
                # 触发外部传入的回调函数，物理入库 pending_approvals 并获取审批单号
                approval_id = on_approval_required(
                    context.tool_call_id,
                    context.tool_name,
                    context.tool_args,
                    context.extra.get("saved_messages"),
                    context.extra.get("current_index", 0),
                )
            
            id_val = approval_id or context.tool_args
            # 抛出特定异常，断流管道并挂起执行
            raise ApprovalRequiredException(id_val)

        return await next_call()