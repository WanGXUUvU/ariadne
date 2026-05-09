# TASK-039 - Memory 层

## 目标
建立最小 memory 机制，让 agent 可以保存长期偏好、项目事实和用户约定。

## 产品层
Memory

## 范围内
- 定义 memory record
- 支持 project memory 和 session memory
- 支持写入、读取、删除
- prompt 构造时注入少量 relevant memory
- 提供手动管理 API

## 范围外
- 向量数据库
- 自动复杂检索
- 多用户隐私策略

## 实现步骤
1. 新增 memory ORM model 和 migration。
2. 定义 memory 类型：preference、fact、instruction。
3. 新增 memory service。
4. 在 prompt 构造时读取少量 memory。
5. 写测试确认 memory 能保存并进入 prompt。

## 完成标准
- 用户约定可以跨 session 保留。
- memory 注入有数量限制。
- memory 可以删除。

## 验证
- `alembic upgrade head`
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- 是否区分 session 和 project。
- 是否避免无限注入 memory。
- 是否给用户可控删除能力。

