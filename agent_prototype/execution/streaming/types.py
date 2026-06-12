"""
[九层模型 - L8 执行层 - 流式子模块]

SSE 推送帧的结构定义。

StreamFrame 原先寄生在 api/dto/schemas.py 中，事实上仅被 execution/streaming
内部使用。归位到本模块以消除 L8 → API 层的反向依赖。
"""

from typing import Any, Literal
from pydantic import BaseModel


class StreamFrame(BaseModel):
    """一条 SSE 推送帧的结构。

    type 取值：
    - start          : 运行开始，包含 session_id / run_id / agent_name
    - agent_event    : 一个语义事件（工具调用 / 工具结果 / 工具错误）
    - delta          : 最终回答阶段的 token 级增量内容
    - end            : 运行完成，包含完整 reply / state / metadata
    - error          : 运行失败，包含错误码和错误信息
    - paused         : 运行因审批暂停，包含 run_id
    - resume         : 审批通过后恢复运行，包含 run_id
    - thinking_delta : 思考过程的 token 级增量内容
    """

    type: Literal[
        "start",
        "agent_event",
        "delta",
        "end",
        "error",
        "paused",
        "resume",
        "thinking_delta",
    ]
    data: dict[str, Any]
