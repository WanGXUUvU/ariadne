# TASK-021 - API 输出整理

## 目标
统一 `/run` 返回结构，让前端、CLI、测试都能稳定消费。

## 产品层
API

## 范围内
- 明确 `reply`
- 明确 `state` 或 state summary
- 明确 `events`
- 明确 `metadata`
- 明确错误返回结构

## 范围外
- streaming
- 前端 UI
- OpenAPI 文档美化

## 实现步骤
1. 审查当前 `AgentOutput`。
2. 增加 response metadata：session_id、agent_name、skill_name、run_id。
3. 确保 events schema 稳定。
4. 对常见错误使用统一错误响应。
5. 更新测试断言。

## 完成标准
- `/run` 返回字段稳定。
- 用户不需要从 state 里猜关键信息。
- 错误响应可读。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- response 是否过大。
- 是否兼容前端和 CLI。
- 是否为 streaming 留接口。
