"""接口与适配层 (Interface Layer) - 压缩路由控制器

职责：
1. 提供历史消息压缩（Compaction）触发 API。
2. 接收压缩请求入参，支持手动或自动压缩策略转换。

不负责：
1. 文本压缩的 LLM 计算逻辑。
2. 会话历史消息数据库物理标记与清理。

数据流向：
- 输入：HTTP POST 压缩参数。
- 输出：压缩成功结果 JSON 响应。
- 上游来源：前端或自动化压缩策略调度。
- 下游流向：调用 agent_prototype/memory/summary/service.py。
"""

from fastapi import APIRouter, Depends, status

from agent_prototype.core.types import CompactInput, CompactOutput
from agent_prototype.memory.summary.service import CompactService
from agent_prototype.api.routes.dependencies import error_response, get_compact_service

router = APIRouter()


@router.post("/compact", response_model=CompactOutput)
def compact_session_api(payload: CompactInput, service: CompactService = Depends(get_compact_service)) -> CompactOutput:
    """这个函数是用来手动触发会话历史消息压缩（瘦身）的。
    
    当聊天记录太长、太占内存或者容易超出大模型 Token 限制时，调用这个接口可以把老的消息进行摘要压缩，只留下关键信息。
    
    Need 拿到的东西：
    - payload: CompactInput 对象，里面包含了要压缩哪一个会话（session_id）以及具体的压缩策略和参数。
    - service: CompactService 实例，由依赖注入提供。
    
    会给出来的结果：
    - CompactOutput 对象，里面会告诉你压缩是否成功，以及压缩后的摘要内容或者精简后的状态。
    """
    try:
        return service.compact_session(payload)
    except ValueError as exc:
        return error_response(status.HTTP_400_BAD_REQUEST, "bad_request", str(exc))