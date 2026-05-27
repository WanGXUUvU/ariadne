"""工作区核心服务单元测试。

测试 WorkspaceService 的依赖注入构造、选择弹窗的成功与取消响应逻辑。
"""

import unittest
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agent_prototype.infra.db.engine import Base
from agent_prototype.memory.workspace.store import SqliteWorkspaceStore
from agent_prototype.memory.workspace.service import WorkspaceService


class TestWorkspaceService(unittest.TestCase):

    def setUp(self):
        """测试前置热身：创建内存 SQLite 独立连接会话，物理建表"""
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        """测试后置收口：关闭会话，清空物理表，确保测试干净隔离"""
        self.db.close()
        Base.metadata.drop_all(self.engine)

    @patch("agent_prototype.memory.workspace.service.open_folder_dialog")
    def test_select_dialog_success(self, mock_dialog):
        """测试场景 1：用户在 macOS Finder 弹窗中成功选择了一个有效目录"""
        # 1. 模拟物理弹窗返回一个真实存在的绝对路径
        mock_dialog.return_value = "/Users/wangxu/Documents/AGENT Build"
        
        # 2. 调用业务服务接口
        service = WorkspaceService(self.db)
        workspace = service.select_dialog()
        
        # 3. 校验实体状态与智能解析的名称
        self.assertIsNotNone(workspace)
        self.assertEqual(workspace.path, "/Users/wangxu/Documents/AGENT Build")
        self.assertEqual(workspace.name, "AGENT Build")
        
        # 4. 校验物理 Store 的数据落库正确性
        store = SqliteWorkspaceStore(self.db)
        records = store.list_all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].path, "/Users/wangxu/Documents/AGENT Build")

    @patch("agent_prototype.memory.workspace.service.open_folder_dialog")
    def test_select_dialog_cancel(self, mock_dialog):
        """测试场景 2：用户在 macOS Finder 弹窗中点击了 Cancel 按钮取消选择"""
        # 1. 模拟弹窗驱动返回 None
        mock_dialog.return_value = None
        
        # 2. 调用服务接口
        service = WorkspaceService(self.db)
        workspace = service.select_dialog()
        
        # 3. 校验服务正确拦截，不返回任何实体，且不产生任何脏数据入库
        self.assertIsNone(workspace)
        
        store = SqliteWorkspaceStore(self.db)
        self.assertEqual(len(store.list_all()), 0)