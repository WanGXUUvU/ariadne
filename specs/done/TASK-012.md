# TASK-012 - 工具错误事件

## 目标
当工具执行失败时，trace 中要有结构化错误事件，而不是只有异常或字符串。

## 产品层
Trace / Tool Runtime

## 范围内
- 新增 `tool_error` event type
- 捕获工具不存在、参数错误、运行异常
- API 返回中包含错误事件
- Agent 可以继续给出最终回答或明确失败

## 范围外
- 自动重试
- 复杂错误分类
- 远程工具错误

## 实现步骤
1. 扩展 `AgentEvent` 类型。
2. 在 tool registry 执行入口捕获错误。
3. 将错误转换为稳定结构：tool_name、message、code。
4. 修改 Agent 主循环，把 tool error 作为工具结果反馈给模型或直接结束。
5. 测试未知工具和参数错误。

## 完成标准
- 工具失败不会直接让 API 500。
- trace 中能看到失败的工具名和原因。
- 现有成功路径不变。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- 是否避免把 Python traceback 暴露给用户。
- error code 是否稳定。
- 是否保留 debug 排查所需信息。

