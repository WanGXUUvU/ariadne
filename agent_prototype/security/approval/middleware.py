"""人工审批拦截中间件。

职责：
1. 仅在需要时（如 standard 档位下的 DANGER 工具）拦截工具；
2. 触发外部观察者回调进行 pending_approvals 的持久化，并抛出控制流中断异常。
"""

import logging
from typing import Awaitable, Callable

from agent_prototype.model.types.domain import ToolResult
from agent_prototype.security.policy import ApprovalPolicy, needs_approval
from agent_prototype.security.middleware.base import BaseMiddleware
from agent_prototype.security.middleware.base import ToolCallContext

logger = logging.getLogger(__name__)


class ApprovalRequiredException(Exception):
    """当工具调用需要审批拦截时抛出的特定控制流中断异常。
    
    这是一个“审批拉闸异常”。
    当 AI 想要调用的某个工具有点危险（比如删库、发邮件等敏感写操作），而且安全策略规定必须经过人工同意时，系统就会故意扔出这个“异常”，像拉电闸一样瞬间暂停正在执行的代码，把 AI 定在那里，等待人类管理员点下“同意”或“拒绝”。
    """

    def __init__(self, approval_id: str):
        """初始化这个拉闸异常，并记下这张审批单的编号。

        需要拿到的东西：
        - approval_id (str): 审批单的 ID 编号。
        """
        self.approval_id = approval_id
        super().__init__(f"Approval required: {approval_id}")


class ApprovalMiddleware(BaseMiddleware):
    """人工审批中间件。
    
    这个类是一个“安全安检站（审批中间件）”。
    当 AI 尝试运行任何工具时，都必须经过这个安检站。它会检查这个工具的风险级别，如果属于危险操作（比如写磁盘），且系统当前的安全策略不是“完全信任”，它就会在数据库里生成一张“待审批单”（pending_approval），然后无情地抛出 `ApprovalRequiredException` 异常，把当前的执行流程强行挂起，等管理员审批。
    """

    async def call(
        self,
        context: ToolCallContext,
        next_call: Callable[[], Awaitable[ToolResult]],
    ) -> ToolResult:
        """这是安检站值班的具体检查动作。
        它会看一看即将调用的工具和安全参数，判断需不需要拦截。需要的话就生成审批单并抛异常拉闸；不需要的话，就大声喊“放行！”，让下一个安检环节（或者真正执行工具的函数）继续跑下去。

        需要拿到的东西：
        - context (ToolCallContext): 当前准备调用的工具的上下文（包含工具名、喂给它的参数、以及当前的会话安全策略等）。
        - next_call (Callable): 代表下一个安检关卡（或真正执行逻辑）的函数。

        会给出来的结果：
        - ToolResult: 工具最终运行的结果（如果没有被拦截且顺利跑完的话）。如果中途触发审批被拦截了，它会抛出 `ApprovalRequiredException` 异常，根本不会有返回值。
        """
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