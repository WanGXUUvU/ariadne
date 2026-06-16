# TASK-046 - 审批与文件操作审计日志

## 目标
记录关键安全动作，让用户之后可以追踪 agent 做过什么、谁审批了什么、哪些文件被访问或提议修改。

## 产品层
Audit / Safety

## 范围内
- 新增 audit log 数据表或 JSON 存储结构
- 记录工具审批、文件读取、文件修改草案
- 每条日志包含时间、session、action、target、result
- 提供查询接口

## 范围外
- 企业级审计
- 多用户身份系统
- 日志导出

## 实现步骤
1. 设计 `AuditLogRecord` 数据模型。
2. 增加 Alembic migration。
3. 在审批流程和文件工具中写入 audit log。
4. 新增 `/audit` 查询接口，先按 session 过滤。
5. 写测试确认关键动作会留下日志。

## 完成标准
- 审批和文件访问有可追踪记录。
- 日志不会影响主流程失败。
- 查询结果按时间排序。

## 验证
- `alembic upgrade head`
- `python3 -m unittest backend.tests.test_agent -v`

## Review 检查点
- 日志是否稳定且字段少。
- 是否避免记录敏感完整内容。
- 写日志失败是否会破坏主流程。

