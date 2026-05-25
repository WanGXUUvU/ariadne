# ── 标准库 ────────────────────────────────────────────────────────────────────
import uuid
from typing import Optional

# ── 第三方库 ──────────────────────────────────────────────────────────────────
from sqlalchemy.orm import Session

# ── 本地模块 ──────────────────────────────────────────────────────────────────
from agent_prototype.core.schemas import PROFILES
from agent_prototype.interface.dto.schemas import (
    AgentState, ApprovalPolicy, CreateSessionInput,
    PermissionProfile, RenameSessionInput, ResetInput,
    SandboxMode, SessionSummary,
)
from agent_prototype.infrastructure.database.models import ModelSetting, ProviderConfig
from agent_prototype.infrastructure.database.repositories.session_store import SqliteSessionStore


class SessionService:
    """会话生命周期管理服务类 (OOP)
    
    职责：
    1. 负责会话的创建、销毁、重置、重命名；
    2. 控制会话的模型绑定及安全档位权限参数更改，并管理事务控制。
    """
    
    def __init__(self, db: Session):
        self.db    = db
        self.store = SqliteSessionStore(db)

    # ── 会话生命周期 ────────────────────────────────────────────────────────────

    def create_session(self, payload: CreateSessionInput) -> SessionSummary:
        """创建一个全新的空白会话"""
        session_id = uuid.uuid4().hex
        state = AgentState()

        # 尝试填入默认提供商与启用模型
        default_provider = self.db.query(ProviderConfig).filter(ProviderConfig.is_default == 1).first()
        default_provider_id = None
        default_model_id = None
        
        if default_provider:
            default_model = self.db.query(ModelSetting).filter(
                ModelSetting.provider_id == default_provider.id,
                ModelSetting.enabled == 1,
            ).first()
            default_provider_id = default_provider.id
            default_model_id = default_model.model_id if default_model else None

        try:
            record = self.store.upsert_session_snapshot(
                session_id,
                state=state,
                session_name=payload.session_name,
                last_agent_name=None,
                last_skill_name=None,
                last_reply_preview=None,
                workspace_path=payload.workspace_path,
                workspace_name=payload.workspace_name,
            )
            record.model_provider_id = default_provider_id
            record.model_id = default_model_id
            self.db.commit()
            self.db.refresh(record)
        except Exception:
            self.db.rollback()
            raise

        return SessionSummary(
            session_id=record.session_id,
            session_name=record.session_name,
            created_at=record.created_at,
            updated_at=record.updated_at,
            last_agent_name=record.last_agent_name,
            last_skill_name=record.last_skill_name,
            message_count=record.message_count,
            last_reply_preview=record.last_reply_preview,
            permission_profile=record.permission_profile,
            workspace_path=record.workspace_path,
            workspace_name=record.workspace_name,
        )

    def reset_session(self, payload: ResetInput) -> dict[str, bool]:
        """重置指定会话，彻底清空其快照消息，并保持其他配置不动"""
        record = self.store.read_session_record(payload.session_id)
        if not record:
            raise ValueError("Session not found")
        
        empty_state = AgentState()
        try:
            self.store.upsert_session_snapshot(
                payload.session_id,
                state=empty_state,
                session_name=record.session_name,
                last_agent_name=None,
                last_reply_preview=None,
                last_skill_name=None,
            )
            # 👇 A-2 联动：将该 session 对应的所有历史运行标记为 inactive
            self.store.reset_session_runs(payload.session_id)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"ok": True}

    def delete_session(self, session_id: str) -> dict[str, bool]:
        """逻辑或物理删除指定会话"""
        record = self.store.read_session_record(session_id)
        if record is None:
            raise ValueError("Session not found")
        
        try:
            self.store.delete_session(session_id)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"ok": True}

    def rename_session(self, session_id: str, new_name: str) -> dict[str, bool]:
        """物理更改会话名称"""
        if not new_name or not new_name.strip():
            raise ValueError("Session name cannot be empty")
        
        record = self.store.read_session_record(session_id)
        if record is None:
            raise ValueError("Session not found")
        
        try:
            self.store.rename_session(session_id, new_name)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"ok": True}

    def update_session(self, session_id: str, payload: RenameSessionInput) -> dict[str, bool]:
        """收归路由越界操作：支持重命名、安全权限档位、模型 ID、服务商 ID、深度思考参数等多维更新"""
        record = self.store.read_session_record(session_id)
        if record is None:
            raise ValueError("Session not found")

        try:
            if payload.session_name is not None:
                if not payload.session_name.strip():
                    raise ValueError("Session name cannot be empty")
                self.store.rename_session(session_id, payload.session_name)
            if payload.permission_profile is not None:
                record.permission_profile = payload.permission_profile
            if payload.model_id is not None:
                record.model_id = payload.model_id
            if payload.model_provider_id is not None:
                record.model_provider_id = payload.model_provider_id
            if payload.thinking_enabled is not None:
                record.thinking_enabled = 1 if payload.thinking_enabled else 0
            if payload.thinking_effort is not None:
                record.thinking_effort = payload.thinking_effort
            if payload.workspace_path is not None:
                record.workspace_path = payload.workspace_path
            if payload.workspace_name is not None:
                record.workspace_name = payload.workspace_name

            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"ok": True}

