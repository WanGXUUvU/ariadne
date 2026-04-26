# TASK-014 - Session 元数据

## 目标
让 session 不只是状态 JSON，还拥有产品级元数据。

## 产品层
会话运行层（Session Runtime）

## 范围内
- 为 session 增加名称、创建时间、更新时间
- 更新 SQLAlchemy model 和 Alembic migration
- 保持旧 session 可读取
- 更新 store 保存逻辑

## 范围外
- 用户账户
- 权限隔离
- 标签和搜索
- 归档

## 完成标准
- session 记录有稳定元数据
- migration 可执行
- 现有 `/run` 和 `/reset` 不受影响

## 验证
- `alembic upgrade head`
- `python3 -m unittest agent_prototype.tests.test_agent -v`
