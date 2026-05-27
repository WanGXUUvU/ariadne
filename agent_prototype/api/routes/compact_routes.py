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
from sqlalchemy.orm import Session

from agent_prototype.api.dto.schemas import CompactInput, CompactOutput
from agent_prototype.memory.summary.service import CompactService
from agent_prototype.infra.db.engine import get_db
from agent_prototype.api.routes.dependencies import error_response

router = APIRouter()


@router.post("/compact", response_model=CompactOutput)
def compact_session_api(payload: CompactInput, db: Session = Depends(get_db)) -> CompactOutput:
    """输入：CompactInput 历史压缩参数、数据库会话。输出：CompactOutput 压缩结果。"""
    try:
        service = CompactService(db)
        return service.compact_session(payload)
    except ValueError as exc:
        return error_response(status.HTTP_400_BAD_REQUEST, "bad_request", str(exc))