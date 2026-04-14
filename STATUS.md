# STATUS

## Current Snapshot
- Phase: 第 1 阶段
- Task: todo-api PATCH schema 修正
- Gate: 轻量记录
- Lane: Fast
- Blocking: None
- Next: 修正 `TodoUpdate` 语法并把 `update_todo` 改成部分更新语义

## This Week
- 目标：把 `todo-api` 从“能跑”整理到“结构更规范”
- 重点：`db.py` / `models.py` / `services.py` / `routes.py`
- 暂不扩展：RAG 新功能、部署、微服务

## Done
- SQLite 版 CRUD 已收口
- SQLAlchemy ORM 基础设施已接上
- `Todo` 模型已定义
- 已理解 `Todo` 类、ORM 对象和数据表映射关系
- ORM 版 CRUD 已实现
- `routes.py` 与 `services.py` 已完成参数对齐
- `TodoCreate` 字段约束已开始引入

## Risks
- ORM 里手动开关 session 还不够规范
- 容易把分支状态和代码状态混淆
