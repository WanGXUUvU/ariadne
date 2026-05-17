# TASK-016 - Trace 回放接口

## 目标
提供按 session 读取历史 trace 的接口，让用户能回看 agent 执行过程。

## 产品层
Trace / API

## 范围内
- 保存每次 run 的 events
- `GET /sessions/{session_id}/trace`
- 支持按 run_id 过滤
- 返回事件顺序稳定

## 范围外
- 实时 streaming
- 复杂时间线查询
- 可视化 UI

## 实现步骤
1. 确认当前 events 是否只在 response 中返回，若未持久化则新增存储。
2. 设计 trace record 或嵌入 session state 的方案。
3. 每次 run 后保存 events。
4. 新增 trace API。
5. 测试多次 run 的事件顺序。

## 完成标准
- 历史执行轨迹可重新读取。
- trace 和 session/run 有明确关联。
- 事件 schema 复用现有 `AgentEvent`。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- 是否避免重复存储过多内容。
- run_id 是否为后续后台任务留接口。
- trace 事件是否向后兼容。

