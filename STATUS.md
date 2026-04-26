# STATUS

## Current Status
- Phase: planning
- Task: specs/TASK-003.md
- Gate: Draft
- Allowed Now: start-implementation
- Lane: Fast
- Blocked: None
- Next action: 先把 `routes.py` / `services.py` 的导入、签名、表初始化接通，再跑通 `/run` 和 `/reset`。

## 遗留项
- 见 `specs/TASK-002.md`

## History
| Date | Task | Gate Passed | Notes |
|------|------|-------------|-------|
| 2026-04-24 | 完成第一个工具调用闭环 | Verify / Review | 已跑通 `tool_calls -> tool -> final`，并用 `curl` 验证。 |
| 2026-04-24 | 规划会话隔离任务 | implementation | 已确认当前原型需要按 `session_id` 隔离状态，进入下一阶段。 |
| 2026-04-24 | 实现会话隔离与重置 | implementation | 已改为按 `session_id` 读写内存会话状态，并提供 `/reset`。 |
| 2026-04-24 | 手动验证会话隔离 | Verify | `A` 可续上下文，`B` 独立，`/reset` 后 `A` 重新开始。 |
| 2026-04-24 | `TASK-002` 功能收口 | Review | 会话隔离与重置功能完成，测试按当前安排延期。 |
| 2026-04-24 | 回归验证失败 | Verify | `unittest` 运行失败，`AgentInput` 还缺 `session_id`，测试未同步。 |
| 2026-04-24 | 回归验证通过 | Verify | `python3 -m unittest agent_prototype.tests.test_agent -v` 通过。 |
| 2026-04-24 | 创建下一张任务卡 | planning | 新增 `specs/TASK-003.md`，聚焦会话持久化。 |
| 2026-04-24 | 确认存储方案 | planning | `TASK-003` 先走 SQLite，不上更重的数据库。 |
| 2026-04-26 | 开始接通 SQLite 链路 | implementation | 已有 `db.py`、`models.py`、`session_store.py`、`services.py`，下一步是修正接口引用并初始化表。 |
