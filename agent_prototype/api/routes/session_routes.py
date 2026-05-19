from fastapi import APIRouter, Depends, status  # 导入路由、依赖和状态码
from sqlalchemy.orm import Session  # 导入数据库会话
from ...core.schemas import CreateSessionInput, SessionDetail, SessionSummary,RenameSessionInput  # 导入 schema
from ...application.session_service import create_session_service, delete_session_service,rename_session_service  # session 生命周期服务
from ...storage.db import get_db  # 导入数据库依赖
from ...storage.stores.session_store import SqliteSessionStore  # 导入 session store
from .common import error_response  # 导入统一错误响应

router = APIRouter()  # 创建本文件路由器

@router.post("/sessions", response_model=SessionSummary)  # 定义创建 session
def create_session_api(payload: CreateSessionInput, db: Session = Depends(get_db)) -> SessionSummary:  # 接收创建请求
    """输入：CreateSessionInput 和数据库会话。输出：SessionSummary。"""  # 接口说明
    return create_session_service(payload, db)  # 交给 service 处理

@router.delete("/sessions/{session_id}")  # 定义删除 session
def delete_session_api(session_id: str, db: Session = Depends(get_db)) -> dict[str, bool]:  # 接收 session_id
    """输入：session_id 和数据库会话。输出：是否删除成功。"""  # 接口说明
    try:  # 捕获业务错误
        return delete_session_service(session_id, db)  # 交给 service 处理
    except ValueError as exc:  # 捕获业务错误
        return error_response(status.HTTP_400_BAD_REQUEST, "bad_request", str(exc))  # 返回统一错误

@router.get("/sessions", response_model=list[SessionSummary])  # 定义列表接口
def list_sessions_api(db: Session = Depends(get_db)) -> list[SessionSummary]:  # 注入数据库会话
    """输入：数据库会话。输出：SessionSummary 列表。"""  # 接口说明
    store = SqliteSessionStore(db)  # 创建 session store
    records = store.list_sessions()  # 读取 session 列表
    return [  # 转成 API schema
        SessionSummary(  # 构造 summary
            session_id=record.session_id,  # session id
            session_name=record.session_name,  # session 名称
            created_at=record.created_at,  # 创建时间
            updated_at=record.updated_at,  # 更新时间
            last_agent_name=record.last_agent_name,  # 最近 agent
            last_skill_name=record.last_skill_name,  # 最近 skill
            message_count=record.message_count,  # 消息数
            last_reply_preview=record.last_reply_preview,  # 回复预览
            permission_profile=record.permission_profile,  # 权限档位
        )  # 单条 summary 结束
        for record in records  # 遍历数据库记录
    ]  # 列表结束

@router.get("/sessions/{session_id}", response_model=SessionDetail)  # 定义详情接口
def read_session_api(session_id: str, db: Session = Depends(get_db)) -> SessionDetail:  # 注入 session_id 和 DB
    """输入：session_id 和数据库会话。输出：SessionDetail。"""  # 接口说明
    store = SqliteSessionStore(db)  # 创建 store
    record = store.read_session_record(session_id)  # 读取 session 记录
    if record is None:  # 找不到记录
        return error_response(status.HTTP_404_NOT_FOUND, "session_not_found", "Session not found")  # 返回 404
    state = store.read_session_state(session_id)  # 读取 session state
    if state is None:  # state 丢失
        return error_response(status.HTTP_404_NOT_FOUND, "session_not_found", "Session not found")  # 返回 404
    return SessionDetail(  # 组装详情响应
        session_id=record.session_id,  # session id
        session_name=record.session_name,  # session 名称
        created_at=record.created_at,  # 创建时间
        updated_at=record.updated_at,  # 更新时间
        last_agent_name=record.last_agent_name,  # 最近 agent
        last_reply_preview=record.last_reply_preview,  # 最近回复摘要
        last_skill_name=record.last_skill_name,  # 最近 skill
        message_count=record.message_count,  # 消息数
        state=state,  # session state
        permission_profile=record.permission_profile,  # 权限档位
    )  # 响应结束

@router.patch("/sessions/{session_id}")
def rename_session_api(session_id:str,payload:RenameSessionInput,db:Session=Depends(get_db))->dict[str,bool]:
    try:
        return rename_session_service(session_id,payload.session_name,db)
    except ValueError as exc:
        return error_response(status.HTTP_400_BAD_REQUEST,"bad_request",str(exc))