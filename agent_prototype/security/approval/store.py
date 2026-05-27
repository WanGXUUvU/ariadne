"""应用服务层 (Application Layer) - 审批持久化仓储

职责：
1. 维护人工审批工单在数据库中的持久化生命周期（创建、查询、更新状态）。
2. 提供强一致性的审批决策存储访问对象。

不负责：
1. 拦截器的安全决策和中间件触发。
2. 前端事件的推送。

数据流向：
- 输入：审批记录的 CRUD 属性。
- 输出：数据库持久化审批模型实体。
- 上游来源：agent_prototype/security/approval/service.py。
- 下游流向：通过 DB Engine 写入 SQLite。
"""

import uuid,json
from typing import Optional

from sqlalchemy.orm import Session

from agent_prototype.infra.db.orm_models import PendingApproval
from agent_prototype.api.dto.schemas import ChatMessage

class SqliteApprovalStore:
    """SQLite 审批持久化仓储类
    
    这个类是“审批工单数据库管家”。
    专门负责在数据库的“待审批表”（PendingApproval）里打杂，比如：AI 调用敏感工具时，在这个表里登记一张包含当前聊天进度和工具参数的全新“审批工单”；根据单号（approval_id）查询工单详情；工单被主人批准或驳回后更新工单状态；以及在需要重跑的时候把工单里存的聊天历史重新还原出来。
    """

    def __init__(self, db: Session):
        """工单仓储初始化，把操作数据库的“钥匙”拿好。

        需要拿到的东西：
        - db (Session): 数据库会话连接。
        """
        self.db = db
    
    def create(
            self,
            session_id: str,
            run_id: str,
            tool_name: str,
            tool_call_id: str,
            arguments: str,
            saved_messages: list[ChatMessage],
            event_index: int,
    ) -> PendingApproval:
        """在数据库里生成并登记一张全新的“待审批工单”。
        它会随机生成一个唯一的审批单号，把会话 ID、运行 ID、想跑的工具名字、传给工具的参数、当前的聊天上下文历史和执行步骤索引通通记录在案，状态标记为“等待审批（pending）”。

        需要拿到的东西：
        - session_id (str): 属于哪个聊天会话。
        - run_id (str): 属于哪次运行。
        - tool_name (str): 敏感工具的名字。
        - tool_call_id (str): 该工具调用的标识 ID。
        - arguments (str): 工具调用的参数 JSON 文本。
        - saved_messages (list[ChatMessage]): 当前断开时的完整聊天消息历史（用于后面恢复重跑）。
        - event_index (int): 拦截时已经运行到第几个步骤事件。

        会给出来的结果：
        - PendingApproval: 刚在数据库里建好的审批记录对象。
        """
        record=PendingApproval(
            id=uuid.uuid4().hex,
            session_id=session_id,
            run_id=run_id,
            tool_name=tool_name,
            tool_call_id=tool_call_id,
            arguments=arguments,
            status="pending",
            saved_messages=[saved_message.model_dump(exclude_none=True) for saved_message in saved_messages],
            event_index=event_index,
        )

        self.db.add(record)

        return record
    
    def get(self, approval_id: str) -> Optional[PendingApproval]:
        """根据单号（ID）把对应的审批工单完整地从数据库里查出来。

        需要拿到的东西：
        - approval_id (str): 审批单号 ID。

        会给出来的结果：
        - Optional[PendingApproval]: 对应的审批记录，如果找不到就返回 None。
        """
        return (self.db.query(PendingApproval).filter(PendingApproval.id==approval_id).first())
    
    def update_status(self, approval_id: str, status: str) -> Optional[PendingApproval]:
        """更改审批工单的状态（比如从“pending 待处理”变成“approved 已批准”或“rejected 已拒绝”）。

        需要拿到的东西：
        - approval_id (str): 审批单号 ID。
        - status (str): 新的状态值。

        会给出来的结果：
        - Optional[PendingApproval]: 修改好状态后的审批记录，如果没查到这个单子就返回 None。
        """
        record=self.get(approval_id)
        if record is None:
            return None
        record.status=status
        return record
    
    def restore_messages(self, approval: PendingApproval) -> list[ChatMessage]:
        """把审批工单里序列化保存的聊天历史消息还原出来，还原成 Python 能看懂的 `ChatMessage` 列表，方便系统拿着它继续往下执行对话。

        需要拿到的东西：
        - approval (PendingApproval): 数据库里的审批工单对象。

        会给出来的结果：
        - list[ChatMessage]: 还原后的聊天历史消息列表。
        """
        return [ChatMessage.model_validate(msg) for msg in approval.saved_messages]