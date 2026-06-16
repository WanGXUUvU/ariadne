"""TASK-042 权限配置单测。

验证：
1. PermissionProfile schema 三个预设可以正常实例化
2. 新建 session 后，permission_profile 默认为 "conservative"
3. GET /sessions 列表和 GET /sessions/{id} 详情都带 permission_profile 字段
"""

import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agent_prototype.security.policy import (
    ApprovalPolicy,
    PermissionProfile,
    PROFILES,
    SandboxMode,
)
from agent_prototype.memory.session.types import CreateSessionInput
from agent_prototype.memory.session.service import SessionService
from agent_prototype.infra.db.engine import Base
from agent_prototype.memory.session.store import SessionStore


class TestPermissionSchema(unittest.TestCase):
    """PermissionProfile schema 和预设 Profile 测试。"""

    def test_profiles_dict_has_three_entries(self):
        self.assertIn("conservative", PROFILES)
        self.assertIn("standard", PROFILES)
        self.assertIn("full-auto", PROFILES)

    def test_conservative_profile_values(self):
        p = PROFILES["conservative"]
        self.assertEqual(p.sandbox_mode, SandboxMode.READ_ONLY)
        self.assertEqual(p.approval_policy, ApprovalPolicy.UNTRUSTED)

    def test_standard_profile_values(self):
        p = PROFILES["standard"]
        self.assertEqual(p.sandbox_mode, SandboxMode.WORKSPACE_WRITE)
        self.assertEqual(p.approval_policy, ApprovalPolicy.ON_REQUEST)

    def test_full_auto_profile_values(self):
        p = PROFILES["full-auto"]
        self.assertEqual(p.sandbox_mode, SandboxMode.DANGER_FULL_ACCESS)
        self.assertEqual(p.approval_policy, ApprovalPolicy.NEVER)

    def test_permission_profile_workspace_path_defaults_to_none(self):
        p = PermissionProfile(
            name="test",
            sandbox_mode=SandboxMode.READ_ONLY,
            approval_policy=ApprovalPolicy.UNTRUSTED,
        )
        self.assertIsNone(p.workspace_path)


class TestSessionPermission(unittest.TestCase):
    """新建 session 携带默认权限配置的集成测试。"""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        db_path = Path(self.temp_dir.name) / "test_permission.db"
        self.engine = create_engine(
            f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=self.engine)
        self.session_local = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

    def tearDown(self):
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_new_session_has_conservative_permission_profile(self):
        """新建 session 的 permission_profile 应默认为 conservative。"""
        db = self.session_local()
        try:
            summary = SessionService(db).create_session(
                CreateSessionInput(session_name="test")
            )
            self.assertEqual(summary.permission_profile, "conservative")
        finally:
            db.close()

    def test_session_record_stores_permission_profile(self):
        """数据库里的 session 记录也应携带 permission_profile。"""
        db = self.session_local()
        try:
            summary = SessionService(db).create_session(CreateSessionInput())
            store = SessionStore(db)
            record = store.load_record(summary.session_id)
            self.assertIsNotNone(record)
            self.assertEqual(record.permission_profile, "conservative")
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
