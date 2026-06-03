import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agent_prototype.infra.db.engine import Base
from agent_prototype.infra.db.orm_models import (
    SessionRecord,
    SessionRunRecord,
    SessionRunEventRecord,
    ToolCallRecord,
    PendingApproval,
)
from agent_prototype.execution.runtime.types import AgentState
from agent_prototype.core.types import ChatMessage
from agent_prototype.memory.session.service import SessionService
from agent_prototype.memory.session.types import CreateSessionInput


class TestSessionTruncate(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.service = SessionService(self.db)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_truncate_session_middle(self):
        # 1. 创建会话并模拟存入多轮对话
        summary = self.service.create_session(CreateSessionInput(session_name="test_truncate"))
        session_id = summary.session_id

        record, state = self.service.get_session(session_id)
        state.messages = [
            ChatMessage(role="system", content="System Prompt"),
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi! How can I help you?"),
            ChatMessage(role="user", content="Tell me a joke"),
            ChatMessage(role="assistant", content="Why did the scarecrow win an award?"),
            ChatMessage(role="user", content="I don't know"),
            ChatMessage(role="assistant", content="Because he was outstanding in his field!"),
        ]
        self.service.store.upsert_session_snapshot(session_id, state)

        # 2. 插入对应的 runs, events, tool calls, pending approvals 记录
        run1 = SessionRunRecord(session_id=session_id, run_id="r1", user_input="Hello", reply="Hi", parent_run_id=None)
        run2 = SessionRunRecord(session_id=session_id, run_id="r2", user_input="Tell me a joke", reply="Why did...", parent_run_id=None)
        run3 = SessionRunRecord(session_id=session_id, run_id="r3", user_input="I don't know", reply="Because...", parent_run_id=None)
        self.db.add_all([run1, run2, run3])
        self.db.commit()

        # 添加一些关联的细节数据用来验证级联清理
        event1 = SessionRunEventRecord(run_id="r1", event_index=0, type="thinking", content="...")
        event2 = SessionRunEventRecord(run_id="r2", event_index=0, type="thinking", content="...")
        event3 = SessionRunEventRecord(run_id="r3", event_index=0, type="thinking", content="...")
        tool_call = ToolCallRecord(run_id="r2", tool_name="web_search", status="completed")
        approval = PendingApproval(id="app1", session_id=session_id, run_id="r3", tool_name="spawn_child_agent", arguments="", event_index=1, saved_messages=[])
        self.db.add_all([event1, event2, event3, tool_call, approval])
        self.db.commit()

        # 3. 在 index=3 处（即第 2 个 user 消息 "Tell me a joke"）截断
        # 按照设计：
        # - messages 被截断为 index[:3] (保留前 3 个：system, Hello, Hi)
        # - user 消息计数 K = 1 (Hello)
        # - 仅保留 K=1 个 run (r1 应该保留，r2 和 r3 应该被删除)
        res = self.service.truncate_session(session_id, 3)
        self.assertTrue(res["ok"])

        # 4. 验证数据库快照与消息数量
        _, updated_state = self.service.get_session(session_id)
        self.assertEqual(len(updated_state.messages), 3)
        self.assertEqual(updated_state.messages[1].content, "Hello")

        # 5. 验证级联清理完成
        all_runs = self.db.query(SessionRunRecord).all()
        self.assertEqual(len(all_runs), 1)
        self.assertEqual(all_runs[0].run_id, "r1")

        all_events = self.db.query(SessionRunEventRecord).all()
        self.assertEqual(len(all_events), 1)
        self.assertEqual(all_events[0].run_id, "r1")

        all_tools = self.db.query(ToolCallRecord).all()
        self.assertEqual(len(all_tools), 0)

        all_approvals = self.db.query(PendingApproval).all()
        self.assertEqual(len(all_approvals), 0)

    def test_truncate_session_all(self):
        # 1. 创建会话并模拟存入多轮对话
        summary = self.service.create_session(CreateSessionInput(session_name="test_truncate"))
        session_id = summary.session_id

        record, state = self.service.get_session(session_id)
        state.messages = [
            ChatMessage(role="system", content="System Prompt"),
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi! How can I help you?"),
            ChatMessage(role="user", content="Tell me a joke"),
            ChatMessage(role="assistant", content="Why did the scarecrow win an award?"),
            ChatMessage(role="user", content="I don't know"),
            ChatMessage(role="assistant", content="Because he was outstanding in his field!"),
        ]
        self.service.store.upsert_session_snapshot(session_id, state)

        # 2. 插入对应的 runs, events, tool calls, pending approvals 记录
        run1 = SessionRunRecord(session_id=session_id, run_id="r1", user_input="Hello", reply="Hi", parent_run_id=None)
        run2 = SessionRunRecord(session_id=session_id, run_id="r2", user_input="Tell me a joke", reply="Why did...", parent_run_id=None)
        run3 = SessionRunRecord(session_id=session_id, run_id="r3", user_input="I don't know", reply="Because...", parent_run_id=None)
        self.db.add_all([run1, run2, run3])
        self.db.commit()

        # 添加一些关联的细节数据用来验证级联清理
        event1 = SessionRunEventRecord(run_id="r1", event_index=0, type="thinking", content="...")
        event2 = SessionRunEventRecord(run_id="r2", event_index=0, type="thinking", content="...")
        event3 = SessionRunEventRecord(run_id="r3", event_index=0, type="thinking", content="...")
        tool_call = ToolCallRecord(run_id="r2", tool_name="web_search", status="completed")
        approval = PendingApproval(id="app1", session_id=session_id, run_id="r3", tool_name="spawn_child_agent", arguments="", event_index=1, saved_messages=[])
        self.db.add_all([event1, event2, event3, tool_call, approval])
        self.db.commit()

        # 3. 在 index=1 处（即第 1 个 user 消息 "Hello"）截断
        # 按照设计：
        # - messages 被截断为 index[:1] (保留前 1 个：system)
        # - user 消息计数 K = 0
        # - 保留 K=0 个 run (r1, r2, r3 都被删除)
        res = self.service.truncate_session(session_id, 1)
        self.assertTrue(res["ok"])

        # 4. 验证数据库快照与消息数量
        _, updated_state = self.service.get_session(session_id)
        self.assertEqual(len(updated_state.messages), 1)

        # 5. 验证级联清理完成
        all_runs = self.db.query(SessionRunRecord).all()
        self.assertEqual(len(all_runs), 0)

        all_events = self.db.query(SessionRunEventRecord).all()
        self.assertEqual(len(all_events), 0)

        all_tools = self.db.query(ToolCallRecord).all()
        self.assertEqual(len(all_tools), 0)

        all_approvals = self.db.query(PendingApproval).all()
        self.assertEqual(len(all_approvals), 0)


if __name__ == "__main__":
    unittest.main()
