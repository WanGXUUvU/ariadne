import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from agent_prototype.infra.db.engine import Base
from agent_prototype.infra.db.orm_models import (
    SessionRecord,
    SessionRunRecord,
    SessionRunEventRecord,
    ToolCallRecord,
)
from agent_prototype.execution.runtime.types import RunState
from agent_prototype.core.types import ChatMessage
from agent_prototype.memory.session.service import SessionService
from agent_prototype.memory.session.types import CreateSessionInput, ForkSessionInput


class TestSessionFork(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.service = SessionService(self.db)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_fork_session_success(self):
        # 1. 创建原会话并注入对话历史记录
        summary = self.service.create_session(
            CreateSessionInput(session_name="my_parent_session")
        )
        parent_id = summary.session_id

        record, state = self.service.get_session(parent_id)
        state.messages = [
            ChatMessage(role="system", content="System Prompt"),
            ChatMessage(role="user", content="Hello"),
            ChatMessage(role="assistant", content="Hi! How can I help you?"),
            ChatMessage(role="user", content="Tell me a joke"),
            ChatMessage(
                role="assistant", content="Why did the scarecrow win an award?"
            ),
        ]
        self.service.store.save_state(parent_id, state)

        # 2. 在原会话中注入 Runs、Events 和 Tool Calls 数据以验证深度拷贝
        run1 = SessionRunRecord(
            session_id=parent_id,
            run_id="r1",
            user_input="Hello",
            reply="Hi",
            parent_run_id=None,
        )
        run2 = SessionRunRecord(
            session_id=parent_id,
            run_id="r2",
            user_input="Tell me a joke",
            reply="Why did...",
            parent_run_id=None,
        )
        self.db.add_all([run1, run2])
        self.db.commit()

        event1 = SessionRunEventRecord(
            run_id="r1", event_index=0, type="thinking", content="Cloning this..."
        )
        event2 = SessionRunEventRecord(
            run_id="r2", event_index=0, type="thinking", content="Discarding this..."
        )
        tool_call = ToolCallRecord(
            run_id="r1", tool_name="web_search", status="completed"
        )
        self.db.add_all([event1, event2, tool_call])
        self.db.commit()

        # 3. 触发派生会话分支 (在 index = 3 处派生，即保留 system, user(Hello), assistant(Hi)，舍弃后面的消息)
        # 此时对应的 K = 1 (Hello)，因此 r1 应被复制，r2 被舍弃
        fork_input = ForkSessionInput(message_index=3)
        fork_summary = self.service.fork_session(parent_id, fork_input)
        forked_id = fork_summary.session_id

        # 4. 验证会话表字段与元数据拷贝
        parent_db = (
            self.db.query(SessionRecord)
            .filter(SessionRecord.session_id == parent_id)
            .first()
        )
        forked_db = (
            self.db.query(SessionRecord)
            .filter(SessionRecord.session_id == forked_id)
            .first()
        )

        self.assertIsNotNone(forked_db)
        self.assertEqual(forked_db.session_name, "fork: my_parent_session")
        self.assertEqual(forked_db.parent_session_id, parent_id)
        self.assertEqual(forked_db.fork_message_index, 3)

        # 5. 验证新会话的历史消息长度与内容
        _, forked_state = self.service.get_session(forked_id)
        self.assertEqual(len(forked_state.messages), 3)
        self.assertEqual(forked_state.messages[1].content, "Hello")

        # 原会话应该完整保存，不受影响
        _, original_state = self.service.get_session(parent_id)
        self.assertEqual(len(original_state.messages), 5)

        # 6. 验证 Runs 以及 Trace 数据克隆
        parent_runs = (
            self.db.query(SessionRunRecord)
            .filter(SessionRunRecord.session_id == parent_id)
            .all()
        )
        forked_runs = (
            self.db.query(SessionRunRecord)
            .filter(SessionRunRecord.session_id == forked_id)
            .all()
        )

        # 原会话的 Runs 应该依旧为 2 个
        self.assertEqual(len(parent_runs), 2)
        # 新分支会话只保留并克隆了 1 个对应 Run
        self.assertEqual(len(forked_runs), 1)

        forked_run = forked_runs[0]
        # 运行 ID 应被生成为全新的 UUID
        self.assertNotEqual(forked_run.run_id, "r1")
        self.assertEqual(forked_run.user_input, "Hello")

        # 验证对应的 Event 和 Tool Call 也被深拷贝并挂载到了新的 run_id 上
        forked_events = (
            self.db.query(SessionRunEventRecord)
            .filter(SessionRunEventRecord.run_id == forked_run.run_id)
            .all()
        )
        self.assertEqual(len(forked_events), 1)
        self.assertEqual(forked_events[0].content, "Cloning this...")

        forked_tools = (
            self.db.query(ToolCallRecord)
            .filter(ToolCallRecord.run_id == forked_run.run_id)
            .all()
        )
        self.assertEqual(len(forked_tools), 1)
        self.assertEqual(forked_tools[0].tool_name, "web_search")

        # 7. 验证独立隔离性 (向新分支添加消息，不会影响父会话)
        forked_state.messages.append(
            ChatMessage(role="user", content="New query in child")
        )
        self.service.store.save_state(forked_id, forked_state)

        # 重读验证
        _, final_original_state = self.service.get_session(parent_id)
        self.assertEqual(len(final_original_state.messages), 5)


if __name__ == "__main__":
    unittest.main()
