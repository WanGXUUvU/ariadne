# TASK-004

## Goal
为当前 SQLite 会话存储补上最小可用的数据库迁移能力，让后续修改 `session_records` 表结构时不必依赖删库重建。

## In Scope
- 理解 `create_all()` 只能建表不能迁移的边界
- 接入 Alembic 迁移工具
- 让 Alembic 识别当前 `Base.metadata`
- 生成并执行第一条迁移
- 保持现有 `/run`、`/reset` 和会话持久化行为不变

## Out of Scope
- 多数据库方言适配
- 分布式迁移
- 复杂回滚和数据转换策略
- 权限与鉴权
- 多 Agent 编排

## Done when
- 能通过迁移脚本创建或升级 `session_records` 表
- 后续表结构调整不再依赖手动删库重建
- 现有会话数据迁移路径清晰
- 当前 SQLite 持久化主流程不受影响
