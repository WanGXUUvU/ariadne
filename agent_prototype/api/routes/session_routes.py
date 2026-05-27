"""接口与适配层 (Interface Layer) - 会话路由控制器

职责：
1. 提供会话（Session）与执行轨迹（Trace）的 CRUD 路由适配。
2. 支持创建会话、会话重命名、删除会话、以及查询会话历史记录。

不负责：
1. 会话与物理文件夹绑定的具体业务动作（由 WorkspaceService 负责）。
2. 底层数据库会话和 Trace 的物理读写。

数据流向：
- 输入：HTTP 路由入参及 Session 动作 DTO。
- 输出：会话对象或历史消息列表。
- 上游来源：前端 sidebar 列表与对话主视窗。
- 下游流向：调用 agent_prototype/memory/session/service.py。
"""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from agent_prototype.api.dto.schemas import CreateSessionInput, SessionDetail, SessionSummary, RenameSessionInput
from agent_prototype.memory.session.service import SessionService
from agent_prototype.infra.db.engine import get_db
from agent_prototype.memory.session.store import SqliteSessionStore
from agent_prototype.api.routes.dependencies import error_response

router = APIRouter()


@router.post("/sessions", response_model=SessionSummary)
def create_session_api(payload: CreateSessionInput, db: Session = Depends(get_db)) -> SessionSummary:
    """这个函数是用来创建一个新的会话（Session）的。
    
    每次你想跟 Agent 开启一段全新的聊天，或者换一个工作区重新做任务时，就用这个接口建一个新会话。
    
    需要拿到的东西：
    - payload: CreateSessionInput 对象，里面包含新会话的名字、使用哪种权限、关联哪个工作区等配置。
    - db: 数据库连接会话，用于将新会话保存到数据库中。
    
    会给出来的结果：
    - SessionSummary 对象，也就是这个新会话的简要基本信息（比如 ID、名字、创建时间等）。
    """
    service = SessionService(db)
    return service.create_session(payload)


@router.delete("/sessions/{session_id}")
def delete_session_api(session_id: str, db: Session = Depends(get_db)) -> dict[str, bool]:
    """这个函数是用来彻底删除某一个不需要的会话的。
    
    调用这个接口后，该会话下的所有聊天历史记录和相关数据都会被清理干净。
    
    需要拿到的东西：
    - session_id: 字符串类型，代表要删除的那个会话的唯一身份证。
    - db: 数据库连接会话，用来去数据库执行删除。
    
    会给出来的结果：
    - 一个字典，形如 {"status": True}，代表删除操作是否成功完成。
    """
    try:
        service = SessionService(db)
        return service.delete_session(session_id)
    except ValueError as exc:
        return error_response(status.HTTP_400_BAD_REQUEST, "bad_request", str(exc))


@router.get("/sessions", response_model=list[SessionSummary])
def list_sessions_api(db: Session = Depends(get_db)) -> list[SessionSummary]:
    """这个函数是用来获取系统里所有会话的摘要列表的。
    
    常用于前端侧边栏（Sidebar）初始化时，展示用户以前聊过的所有会话列表。
    
    需要拿到的东西：
    - db: 数据库连接会话，用来从数据库里捞出所有的会话数据。
    
    会给出来的结果：
    - 一个包含多个 SessionSummary 对象的列表，列表里每个元素都装有对应会话的名字、最后一条消息预览、消息数量等概要信息。
    """
    store = SqliteSessionStore(db)
    records = store.list_sessions()
    return [
        SessionSummary(
            session_id=record.session_id,
            session_name=record.session_name,
            created_at=record.created_at,
            updated_at=record.updated_at,
            last_agent_name=record.last_agent_name,
            last_skill_name=record.last_skill_name,
            message_count=record.message_count,
            last_reply_preview=record.last_reply_preview,
            permission_profile=record.permission_profile,
            context_tokens=record.context_tokens,
            workspace_path=record.workspace_path,
            workspace_name=record.workspace_name,
            session_type=record.session_type,
        )
        for record in records
    ]


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def read_session_api(session_id: str, db: Session = Depends(get_db)) -> SessionDetail:
    """这个函数是用来读取单个会话的极详细内幕信息的（比如它里面的具体聊天消息、使用的模型、是否开启深度思考等）。
    
    需要拿到的东西：
    - session_id: 字符串类型，也就是你要查看的会话的唯一身份证。
    - db: 数据库连接会话，用来读写会话的记录和具体状态。
    
    会给出来的结果：
    - SessionDetail 对象，里面包含了会话的所有细节和完整的历史消息状态。
    """
    store = SqliteSessionStore(db)
    record = store.read_session_record(session_id)
    if record is None:
        return error_response(status.HTTP_404_NOT_FOUND, "session_not_found", "Session not found")
        
    state = store.read_session_state(session_id)
    if state is None:
        return error_response(status.HTTP_404_NOT_FOUND, "session_not_found", "Session not found")
        
    return SessionDetail(
        session_id=record.session_id,
        session_name=record.session_name,
        created_at=record.created_at,
        updated_at=record.updated_at,
        last_agent_name=record.last_agent_name,
        last_reply_preview=record.last_reply_preview,
        last_skill_name=record.last_skill_name,
        message_count=record.message_count,
        state=state,
        permission_profile=record.permission_profile,
        model_id=record.model_id,
        model_provider_id=record.model_provider_id,
        thinking_enabled=bool(record.thinking_enabled),
        thinking_effort=record.thinking_effort or "medium",
        workspace_path=record.workspace_path,
        workspace_name=record.workspace_name,
        session_type=record.session_type,
    )  


@router.patch("/sessions/{session_id}")
def rename_session_api(session_id: str, payload: RenameSessionInput, db: Session = Depends(get_db)) -> dict[str, bool]:
    """这个函数是用来修改会话属性的，比如给会话改个更贴切的新名字，或者更换关联的模型和工作区参数等。
    
    需要拿到的东西：
    - session_id: 字符串类型，你要修改的会话的唯一身份证。
    - payload: RenameSessionInput 对象，里面包含了新的会话名字、选用的模型等要更新的参数。
    - db: 数据库连接会话，用来持久化你的修改。
    
    会给出来的结果：
    - 一个字典，形如 {"status": True}，代表会话信息修改（如改名）是否成功。
    """
    try:
        service = SessionService(db)
        return service.update_session(session_id, payload)
    except ValueError as exc:
        return error_response(status.HTTP_400_BAD_REQUEST, "bad_request", str(exc))