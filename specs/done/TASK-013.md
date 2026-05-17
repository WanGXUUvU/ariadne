# TASK-013 - 工具结果规范化

## 目标
统一工具成功和失败的返回结构，让后续 UI、trace、审批、MCP 都能复用。

## 产品层
Tool Runtime / Trace

## 范围内
- 定义 `ToolResult`
- 包含 `ok`、`content`、`error`、`metadata`
- 所有本地工具返回统一结构
- trace 使用统一结构

## 范围外
- MCP 结果映射
- 文件工具
- 多模态工具结果

## 实现步骤
1. 在 schema 中定义 `ToolResult`。
2. 修改 `echo_tool` 返回结构。
3. 修改 registry 执行入口统一包装结果。
4. 修改 AgentEvent 的 tool result content。
5. 更新测试断言。

## 完成标准
- 工具结果格式稳定。
- 成功和失败都能用同一个 schema 表达。
- UI 不需要猜测返回内容形状。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- schema 是否过度设计。
- 是否保留对 LLM 的简洁 tool message。
- 旧测试是否反映真实行为变化。

