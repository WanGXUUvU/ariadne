"""Run trace 查询服务。

职责：
- 读取 run records 与 event rows。
- 反序列化 ToolResult。
- 组装运行轨迹查询结果。

不负责：
- 不驱动 run 执行。
- 不处理 child agent 调度。
"""

import json
from typing import Optional

from sqlalchemy.orm import Session

from agent_prototype.execution.runtime.types import RunEvent
from agent_prototype.memory.run.store import RunTraceStore
from agent_prototype.tools.result_types import ToolResult


class TraceQueryService:
    """读取并组装会话 trace。"""

    def __init__(self, db: Session, run_store: Optional[RunTraceStore] = None):
        self.db = db
        self.run_store = run_store or RunTraceStore(db)

    def get_session_trace(self, session_id: str, run_id: Optional[str] = None):
        """返回指定 session 的 run_records 和 events_map。"""
        run_records = self.run_store.list_run_records(session_id, run_id=run_id)
        if not run_records:
            return [], {}

        events_map: dict[str, list[RunEvent]] = {}
        for run_record in run_records:
            event_rows = self.run_store.list_run_events(run_record.run_id)
            events = []
            for row in event_rows:
                tool_result = None
                if row.tool_result_json:
                    tool_result = ToolResult.model_validate(json.loads(row.tool_result_json))
                events.append(
                    RunEvent(
                        index=row.event_index,
                        type=row.type,
                        content=row.content,
                        tool_name=row.tool_name,
                        tool_call_id=row.tool_call_id,
                        tool_result=tool_result,
                    )
                )
            events_map[run_record.run_id] = events

        return run_records, events_map
