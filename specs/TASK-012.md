# TASK-012 - 工具错误事件

## 目标
把工具执行错误转成结构化事件，而不是让异常直接打断用户视角。

## 产品层
执行轨迹层（Execution Trace）

## 范围内
- 增加 `tool_error` 事件类型
- 捕获未知工具、参数 JSON 错误、handler 错误
- 保留调试信息但不污染最终回复
- 补测试覆盖工具失败

## 范围外
- 自动重试
- 错误恢复策略
- 用户审批流
- 告警系统

## 完成标准
- 工具失败能被 `events` 清楚记录
- API 不返回不可读的内部堆栈
- 成功路径不受影响

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`
