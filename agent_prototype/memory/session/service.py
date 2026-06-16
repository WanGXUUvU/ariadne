"""应用服务层 (Application Layer) - 会话管理服务

职责：
1. 编排会话（Session）与轨迹（Trace）的完整生命周期业务用例。
2. 处理会话创建、会话重命名、物理删除、以及历史消息回放和轨迹查询。

不负责：
1. 物理磁盘文件的直接存取。
2. 底层数据库 SQL 的拼接。

数据流向：
- 输入：会话 ID、新名称等业务入参。
- 输出：组装好的会话数据、消息历史或 Trace 记录。
- 上游来源：agent_prototype/api/routes/session_routes.py。
- 下游流向：协调调用 agent_prototype/memory/session/store.py。
"""

# ── 标准库 ────────────────────────────────────────────────────────────────────
import uuid

# ── 第三方库 ──────────────────────────────────────────────────────────────────
from sqlalchemy.orm import Session

# ── 本地模块 ──────────────────────────────────────────────────────────────────
from agent_prototype.execution.runtime.types import RunState
from agent_prototype.memory.session.types import (
    CreateSessionInput,
    RenameSessionInput,
    ResetInput,
    SessionSummary,
    ForkSessionInput,
)

from agent_prototype.infra.db.orm_models import (
    ModelSetting,
    ProviderConfig,
    PendingApproval,
    ToolCallRecord,
    SessionRunRecord,
    SessionRunEventRecord,
)
from agent_prototype.memory.session.store import SessionStore


class SessionService:
    """会话生命周期管理服务类 (OOP)

    这个类是一个“会话大管家”。它主要用来打理跟“聊天会话”（Session）有关的所有核心业务，比如：创建一个新会话、把会话重置清空、给会话改名字、彻底删除会话，或者更新会话里绑定的模型和安全策略等。它不直接和数据库打交道，而是指挥底下的 store 模块去干活，并且负责管好“事务”（就是保证一连串数据库操作要么全成功，要么有一步失败了就全部退回原样，防止数据搞乱）。
    """

    def __init__(self, db: Session):
        """大管家初始化。把数据库连接和底下的数据仓库（Store）都准备好，方便后面随时读写数据。

        需要拿到的东西：
        - db (Session): 数据库会话连接，也就是操作数据库的“钥匙”。
        """
        self.db = db
        self.store = SessionStore(db)

    # ── 会话生命周期 ────────────────────────────────────────────────────────────

    def create_session(self, payload: CreateSessionInput) -> SessionSummary:
        """创建一个全新、空白的聊天会话。
        这个函数会自动生成一个独一无二的会话 ID，查一下数据库有没有默认的 AI 模型和模型供应商，有的话就自动和这个新会话绑定。然后把这些配置信息存进数据库，最后把新创建的会话信息打包好返还给调用方。

        需要拿到的东西：
        - payload (CreateSessionInput): 创建会话所需的入参。这里面包括会话叫什么名字（session_name）、关联的工作空间路径（workspace_path）和名称（workspace_name），以及会话类型等。

        会给出来的结果：
        - SessionSummary: 一个精简的会话信息包，里面包含了这个新会话的 ID、名字、创建时间、更新时间、包含的消息数量、工作空间等各种常用属性。
        """
        session_id = uuid.uuid4().hex
        state = RunState()

        # 尝试填入默认提供商与启用模型
        default_provider = (
            self.db.query(ProviderConfig).filter(ProviderConfig.is_default == 1).first()
        )
        default_provider_id = None
        default_model_id = None

        if default_provider:
            default_model = (
                self.db.query(ModelSetting)
                .filter(
                    ModelSetting.provider_id == default_provider.id,
                    ModelSetting.enabled == 1,
                )
                .first()
            )
            default_provider_id = default_provider.id
            default_model_id = default_model.model_id if default_model else None

        try:
            record = self.store.save_state(
                session_id,
                state=state,
                session_name=payload.session_name,
                last_agent_name=None,
                last_reply_preview=None,
                workspace_path=payload.workspace_path,
                workspace_name=payload.workspace_name,
                session_type=payload.session_type,
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
            message_count=record.message_count,
            last_reply_preview=record.last_reply_preview,
            permission_profile=record.permission_profile,
            workspace_path=record.workspace_path,
            workspace_name=record.workspace_name,
            session_type=record.session_type,
        )

    def reset_session(self, payload: ResetInput) -> dict[str, bool]:
        """重置指定的会话，把里面的聊天历史、运行轨迹全部擦除干净，变回像新买的手机一样的出厂设置，但会保留会话本身的名字、绑定的模型和安全配置不被删掉。

        需要拿到的东西：
        - payload (ResetInput): 重置入参。最主要的就是会话 ID (session_id)。

        会给出来的结果：
        - dict[str, bool]: 重置成功后返回一个表示搞定的字典，例如 `{"ok": True}`。
        """
        record = self.store.load_record(payload.session_id)
        if not record:
            raise ValueError("Session not found")

        empty_state = RunState()
        try:
            self.store.save_state(
                payload.session_id,
                state=empty_state,
                session_name=record.session_name,
                last_agent_name=None,
                last_reply_preview=None,
            )
            # 👇 A-2 联动：将该 session 对应的所有历史运行标记为 inactive
            self.store.reset_session_runs(payload.session_id)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"ok": True}

    def delete_session(self, session_id: str) -> dict[str, bool]:
        """把一个指定的会话彻底从数据库里删掉（物理删除），并且把它相关的运行历史、步骤轨迹等等也一并清理干净，防止残留垃圾数据。

        需要拿到的东西：
        - session_id (str): 想要删除的那个会话的唯一身份证号（ID）。

        会给出来的结果：
        - dict[str, bool]: 删完之后返回一个表示搞定的字典，例如 `{"ok": True}`。
        """
        record = self.store.load_record(session_id)
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
        """给一个已经存在的会话重新起个名字。比如把“未命名会话”改成“我的智能助手”。

        需要拿到的东西：
        - session_id (str): 需要改名的会话 ID。
        - new_name (str): 新的名字。新名字不能为空或一堆空格。

        会给出来的结果：
        - dict[str, bool]: 改名成功后返回一个表示搞定的字典，例如 `{"ok": True}`。
        """
        if not new_name or not new_name.strip():
            raise ValueError("Session name cannot be empty")

        record = self.store.load_record(session_id)
        if record is None:
            raise ValueError("Session not found")

        try:
            self.store.rename_session(session_id, new_name)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"ok": True}

    def update_session(
        self, session_id: str, payload: RenameSessionInput
    ) -> dict[str, bool]:
        """一站式多功能会话更新。如果想同时改会话名字、切换安全权限档位、换模型、换模型服务商，或者开启/关闭深度思考参数，都可以通过这个函数一次性搞定。

        需要拿到的东西：
        - session_id (str): 要更新的会话 ID。
        - payload (RenameSessionInput): 包含各种可选更新属性的数据包，比如新名字、安全权限级别、模型 ID 等，传了哪个属性就更新哪个，不传的保持不变。

        会给出来的结果：
        - dict[str, bool]: 更新成功后返回一个表示搞定的字典，例如 `{"ok": True}`。
        """
        record = self.store.load_record(session_id)
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

    def list_sessions(self) -> list[SessionSummary]:
        """列出系统中所有会话的摘要列表。

        会给出来的结果：
        - 包含多个 SessionSummary 对象的列表。
        """
        records = self.store.list_sessions()
        return [
            SessionSummary(
                session_id=record.session_id,
                session_name=record.session_name,
                created_at=record.created_at,
                updated_at=record.updated_at,
                last_agent_name=record.last_agent_name,
                message_count=record.message_count,
                last_reply_preview=record.last_reply_preview,
                permission_profile=record.permission_profile,
                context_tokens=record.context_tokens,
                workspace_path=record.workspace_path,
                workspace_name=record.workspace_name,
                session_type=record.session_type,
                parent_session_id=record.parent_session_id,
                fork_message_index=record.fork_message_index,
            )
            for record in records
        ]

    def get_session(self, session_id: str):
        """读取单个会话的详细记录和状态。

        会给出来的结果：
        - 一个元组 (record, state)，如果找不到则返回 (None, None)。
        """
        record = self.store.load_record(session_id)
        if record is None:
            return None, None
        state = self.store.read_session_state(session_id)
        return record, state

    def truncate_session(self, session_id: str, message_index: int) -> dict[str, bool]:
        """截断指定会话的历史。
        根据message_index物理阶段后续所有消息，以及相关的所有表记录"""

        record = self.store.load_record(session_id)
        if record is None:
            raise ValueError("Session not found")

        state = self.store.read_session_state(session_id)
        if not state:
            raise ValueError("Session state not found")

        if message_index < 0 or message_index >= len(state.messages):
            raise ValueError("Invalid message index")

        try:
            state.messages = state.messages[:message_index]
            self.store.save_state(
                session_id,
                state=state,
                session_name=record.session_name,
            )

            top_runs = (
                self.db.query(SessionRunRecord)
                .filter(
                    SessionRunRecord.session_id == session_id,
                    SessionRunRecord.parent_run_id.is_(None),
                )
                .order_by(SessionRunRecord.id.asc())
                .all()
            )

            k = sum(1 for msg in state.messages if msg.role == "user")

            to_delete = top_runs[k:]

            if to_delete:
                run_ids = [r.run_id for r in to_delete]

                self.db.query(PendingApproval).filter(
                    PendingApproval.run_id.in_(run_ids)
                ).delete(synchronize_session=False)
                self.db.query(ToolCallRecord).filter(
                    ToolCallRecord.run_id.in_(run_ids)
                ).delete(synchronize_session=False)
                self.db.query(SessionRunEventRecord).filter(
                    SessionRunEventRecord.run_id.in_(run_ids)
                ).delete(synchronize_session=False)

                # 删除顶层运行本身，以及所有挂载其下的子智能体运行 (parent_run_id)
                self.db.query(SessionRunRecord).filter(
                    SessionRunRecord.run_id.in_(run_ids)
                    | SessionRunRecord.parent_run_id.in_(run_ids)
                ).delete(synchronize_session=False)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {"ok": True}

    def fork_session(
        self, session_id: str, payload: ForkSessionInput
    ) -> SessionSummary:
        """从指定截断点派生出一个新的分支会话"""

        parent_record = self.store.load_record(session_id)
        if parent_record is None:
            raise ValueError("Parent session not found")

        parent_state = self.store.read_session_state(session_id)
        if parent_state is None:
            raise ValueError("Parent session state not found")

        message_index = payload.message_index

        if message_index < 0 or message_index > len(parent_state.messages):
            raise ValueError("Invalid message index")

        forked_messages = parent_state.messages[:message_index]

        forked_state = RunState()
        forked_state.messages = forked_messages

        forked_name = (
            getattr(payload, "session_name", None)
            or f"fork: {parent_record.session_name or 'Untitled'}"
        )
        forked_session_id = uuid.uuid4().hex

        try:
            record = self.store.save_state(
                forked_session_id,
                state=forked_state,
                session_name=forked_name,
                last_agent_name=parent_record.last_agent_name,
                workspace_path=parent_record.workspace_path,
                workspace_name=parent_record.workspace_name,
                session_type=parent_record.session_type,
            )

            record.model_provider_id = parent_record.model_provider_id
            record.model_id = parent_record.model_id
            record.thinking_enabled = parent_record.thinking_enabled
            record.thinking_effort = parent_record.thinking_effort
            record.permission_profile = parent_record.permission_profile

            # 设置派生关联元数据
            record.parent_session_id = session_id
            record.fork_message_index = message_index
            self.db.flush()

            top_runs = (
                self.db.query(SessionRunRecord)
                .filter(
                    SessionRunRecord.session_id == session_id,
                    SessionRunRecord.parent_run_id.is_(None),
                )
                .order_by(SessionRunRecord.id.asc())
                .all()
            )
            # 保留前 K 个运行记录 (对应 retained user 消息数)
            k = sum(1 for msg in forked_messages if msg.role == "user")
            runs_to_clone = top_runs[:k]
            for parent_run in runs_to_clone:
                # 5.1) 克隆主运行记录
                new_run_id = f"run_{uuid.uuid4().hex[:12]}"
                forked_run = SessionRunRecord(
                    session_id=forked_session_id,
                    run_id=new_run_id,
                    parent_run_id=None,
                    run_status=parent_run.run_status,
                    agent_name=parent_run.agent_name,
                    user_input=parent_run.user_input,
                    reply=parent_run.reply,
                    event_count=parent_run.event_count,
                    created_at=parent_run.created_at,
                    finished_at=parent_run.finished_at,
                    is_active=parent_run.is_active,
                )
                self.db.add(forked_run)
                # 5.2) 克隆对应的 Trace 步骤事件
                events = (
                    self.db.query(SessionRunEventRecord)
                    .filter(SessionRunEventRecord.run_id == parent_run.run_id)
                    .all()
                )
                for ev in events:
                    forked_ev = SessionRunEventRecord(
                        run_id=new_run_id,
                        event_index=ev.event_index,
                        type=ev.type,
                        content=ev.content,
                        tool_name=ev.tool_name,
                        tool_call_id=ev.tool_call_id,
                        tool_result_json=ev.tool_result_json,
                    )
                    self.db.add(forked_ev)
                # 5.3) 克隆对应的工具调用流水
                tool_calls = (
                    self.db.query(ToolCallRecord)
                    .filter(ToolCallRecord.run_id == parent_run.run_id)
                    .all()
                )
                for tc in tool_calls:
                    forked_tc = ToolCallRecord(
                        run_id=new_run_id,
                        tool_name=tc.tool_name,
                        tool_call_id=tc.tool_call_id,
                        status=tc.status,
                        input_json=tc.input_json,
                        result_json=tc.result_json,
                        started_at=tc.started_at,
                        finished_at=tc.finished_at,
                    )
                    self.db.add(forked_tc)
                # 5.4) 克隆关联的子智能体运行记录
                child_runs = (
                    self.db.query(SessionRunRecord)
                    .filter(SessionRunRecord.parent_run_id == parent_run.run_id)
                    .all()
                )
                for child_run in child_runs:
                    child_new_run_id = f"run_{uuid.uuid4().hex[:12]}"
                    forked_child = SessionRunRecord(
                        session_id=forked_session_id,
                        run_id=child_new_run_id,
                        parent_run_id=new_run_id,  # 关联到克隆出来的父运行 ID
                        run_status=child_run.run_status,
                        agent_name=child_run.agent_name,
                        user_input=child_run.user_input,
                        reply=child_run.reply,
                        event_count=child_run.event_count,
                        created_at=child_run.created_at,
                        finished_at=child_run.finished_at,
                        is_active=child_run.is_active,
                    )
                    self.db.add(forked_child)
                    # 克隆子智能体运行的 Events & Tool Calls
                    child_events = (
                        self.db.query(SessionRunEventRecord)
                        .filter(SessionRunEventRecord.run_id == child_run.run_id)
                        .all()
                    )
                    for cev in child_events:
                        forked_cev = SessionRunEventRecord(
                            run_id=child_new_run_id,
                            event_index=cev.event_index,
                            type=cev.type,
                            content=cev.content,
                            tool_name=cev.tool_name,
                            tool_call_id=cev.tool_call_id,
                            tool_result_json=cev.tool_result_json,
                        )
                        self.db.add(forked_cev)
                    child_tool_calls = (
                        self.db.query(ToolCallRecord)
                        .filter(ToolCallRecord.run_id == child_run.run_id)
                        .all()
                    )
                    for ctc in child_tool_calls:
                        forked_ctc = ToolCallRecord(
                            run_id=child_new_run_id,
                            tool_name=ctc.tool_name,
                            tool_call_id=ctc.tool_call_id,
                            status=ctc.status,
                            input_json=ctc.input_json,
                            result_json=ctc.result_json,
                            started_at=ctc.started_at,
                            finished_at=ctc.finished_at,
                        )
                        self.db.add(forked_ctc)
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
            message_count=record.message_count,
            last_reply_preview=record.last_reply_preview,
            permission_profile=record.permission_profile,
            workspace_path=record.workspace_path,
            workspace_name=record.workspace_name,
            session_type=record.session_type,
            parent_session_id=record.parent_session_id,
            fork_message_index=record.fork_message_index,
        )
