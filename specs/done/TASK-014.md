# TASK-014 - Session 元数据

## 目标
为 session 增加用户可见元数据，为列表、搜索、fork、resume、UI 做准备。

## 产品层
Session

## 范围内
- session name
- created_at
- updated_at
- last_agent_name
- last_skill_name
- message_count
- last_reply_preview

## 范围外
- 多用户 owner
- 标签系统
- 全文搜索

## 实现步骤
1. 扩展 ORM model 和 migration。
2. 新建或更新 session 时维护 created/updated。
3. 每次 run 后更新 message_count 和 preview。
4. 记录本轮使用的 agent 和 skill。
5. 测试元数据更新。

## 完成标准
- session 不再只是 state_json。
- 元数据可直接用于列表展示。
- 旧 session 迁移后仍可读取。

## 验证
- `alembic upgrade head`
- `python3 -m unittest backend.tests.test_agent -v`

## Review 检查点
- migration 是否兼容已有 SQLite。
- preview 是否限制长度。
- 元数据是否避免重复计算过重。
