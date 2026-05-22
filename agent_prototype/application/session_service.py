import uuid  # 生成新的 session_id  # 这一行负责唯一 ID
from sqlalchemy.orm import Session  # 数据库会话类型  # 这一行负责事务上下文

from ..core.schemas import AgentState, CreateSessionInput, ResetInput, SessionSummary,PermissionProfile,SandboxMode,ApprovalPolicy, RenameSessionInput  # session 相关 schema  # 这一行负责输入输出类型
from ..storage.stores.session_store import SqliteSessionStore  # session 持久化仓库  # 这一行负责读写数据库记录
from ..storage.models import ProviderConfig, ModelSetting

PROFILES = {
    "conservative": PermissionProfile(
        name="conservative",
        sandbox_mode=SandboxMode.READ_ONLY,
        approval_policy=ApprovalPolicy.UNTRUSTED,
    ),
    "standard": PermissionProfile(
        name="standard",
        sandbox_mode=SandboxMode.WORKSPACE_WRITE,
        approval_policy=ApprovalPolicy.ON_REQUEST,
    ),
    "full-auto": PermissionProfile(
        name="full-auto",
        sandbox_mode=SandboxMode.DANGER_FULL_ACCESS,
        approval_policy=ApprovalPolicy.NEVER,
    ),
}

def create_session_service(payload:CreateSessionInput,db:Session)->SessionSummary:
    """输入：CreateSessionInput 请求对象、数据库会话。输出：新建 session 的摘要信息。"""  # 这个 service 负责创建空白 session，但不运行 agent

    store = SqliteSessionStore(db)
    session_id=uuid.uuid4().hex
    state=AgentState()

    # 查找默认 provider，自动填入初始模型
    default_provider = db.query(ProviderConfig).filter(ProviderConfig.is_default == 1).first()
    default_provider_id = None
    default_model_id = None
    if default_provider:
        default_model = db.query(ModelSetting).filter(
            ModelSetting.provider_id == default_provider.id,
            ModelSetting.enabled == 1,
        ).first()
        default_provider_id = default_provider.id
        default_model_id = default_model.model_id if default_model else None

    try:
        record = store.upsert_session_snapshot(
            session_id,  # 把新生成的 session_id 写入主表
            state=state,  # 先存空 state，后续第一次 /run 再把消息填进去
            session_name=payload.session_name,  # 如果前端传了名字就用它；不传时 store 会回退到 session_id
            last_agent_name=None,  # 新建空会话时还没有运行过 agent
            last_skill_name=None,  # 新建空会话时也还没有使用任何 skill
            last_reply_preview=None,  # 没有回复，自然没有 reply preview
        )
        record.model_provider_id = default_provider_id
        record.model_id = default_model_id
        db.commit()  # 把新 session 真正提交到数据库
        db.refresh(record)  # 刷新 ORM 对象，确保 created_at / updated_at 等数据库字段可读
    except Exception:
        db.rollback()  # 如果创建失败，回滚这次事务，避免留下半成品
        raise

    return SessionSummary(
        session_id=record.session_id,  # 返回新建好的 session_id，前端后续靠它继续操作
        session_name=record.session_name,  # 返回最终生效的会话名；不传时通常会等于 session_id
        created_at=record.created_at,  # 返回创建时间，给列表页直接使用
        updated_at=record.updated_at,  # 新建时更新时间通常等于创建时间
        last_agent_name=record.last_agent_name,  # 空会话还没有最近 agent，应该是 None
        last_skill_name=record.last_skill_name,  # 空会话还没有最近 skill，应该是 None
        message_count=record.message_count,  # 空会话消息数应为 0
        last_reply_preview=record.last_reply_preview,  # 空会话没有最后回复摘要
        permission_profile=record.permission_profile,  # 权限档位，新建默认 conservative
    )


def reset_session_service(payload: ResetInput, db: Session) -> dict[str, bool]:
    """输入：ResetInput 请求对象、数据库会话。输出：是否重置成功的结果字典。"""

    store = SqliteSessionStore(db)
    record = store.read_session_record(payload.session_id)
    if not record:
        raise ValueError("Session not found")
    
    empty_state=AgentState()

    try:
        store.upsert_session_snapshot(
            payload.session_id,
            state=empty_state,
            session_name=record.session_name,
            last_agent_name=None,
            last_reply_preview=None,
            last_skill_name=None,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"ok": True}

def delete_session_service(session_id:str,db:Session)->dict[str,bool]:
    """输入：session_id、数据库会话。输出：是否删除成功的结果字典。"""  # 这个 service 负责真正的删除业务和事务控制

    store=SqliteSessionStore(db)
    record=store.read_session_record(session_id)

    if record is None:
        raise ValueError("Session not found")
    
    try:
        store.delete_session(session_id)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"ok":True}

def rename_session_service(session_id:str,new_name:str,db:Session)->dict[str,bool]:
    store = SqliteSessionStore(db)

    record=store.read_session_record(session_id)

    if not new_name or not new_name.strip():
        raise ValueError("Session name cannot be empty")
    
    if record is None:
        raise ValueError("Session not found")
    
    try:
        store.rename_session(session_id,new_name)
        db.commit()
    
    except Exception:
        db.rollback()
        
        raise

    return{"ok":True}


def update_session_service(session_id: str, payload: RenameSessionInput, db: Session) -> dict[str, bool]:
    """更新 session 配置，支持重命名、修改权限档位、模型 ID、服务商 ID 以及深度思考参数。"""
    store = SqliteSessionStore(db)
    record = store.read_session_record(session_id)
    if record is None:
        raise ValueError("Session not found")

    try:
        if payload.session_name is not None:
            store.rename_session(session_id, payload.session_name)
        if payload.permission_profile is not None:
            record.permission_profile = payload.permission_profile
        if payload.model_id is not None:
            # 支持传入空（即取消绑定）
            record.model_id = payload.model_id
        if payload.model_provider_id is not None:
            record.model_provider_id = payload.model_provider_id
        if payload.thinking_enabled is not None:
            record.thinking_enabled = 1 if payload.thinking_enabled else 0
        if payload.thinking_effort is not None:
            record.thinking_effort = payload.thinking_effort

        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"ok": True}


