# Agent Prototype Quick Manual

这是这个项目的数据库迁移速查版，只保留最常用的用法。

## 平时怎么用

1. 先改 `agent_prototype/models.py`
2. 生成迁移
```bash
alembic revision --autogenerate -m "add xxx"
```
3. 执行迁移
```bash
alembic upgrade head
```
4. 启动应用
```bash
uvicorn agent_prototype.app:app --reload
```

## 常用命令

```bash
alembic revision --autogenerate -m "说明这次改了什么"
alembic upgrade head
alembic current
alembic stamp head
```

## 什么时候用哪个

- `revision --autogenerate`：模型变了，生成迁移文件
- `upgrade head`：把数据库升级到最新版本
- `current`：查看数据库当前版本
- `stamp head`：现有数据库已经有表，只想登记版本，不重复建表

## 你这个项目的特殊点

- 第一次接入 Alembic 时，`agent_session.db` 里可能已经有 `session_records`
- 这种情况下不要直接无脑 `upgrade head`
- 先确认迁移文件写好，再看是否需要先执行 `stamp head`

## 一句话记忆

改模型，出迁移，跑升级。
