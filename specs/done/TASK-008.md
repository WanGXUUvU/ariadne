# TASK-008 - 将 Agent 定义注入 Runtime

## 目标
让 Agent Runtime 使用从持久化层读取的 Agent 定义，而不是完全依赖硬编码 `SYSTEM_PROMPT`。

## 产品层
Agent Runtime / Agent Core

## 范围内
- 在创建 Agent 时传入 Agent 定义
- 用定义中的 instructions 构造 system prompt
- 默认使用 `default` agent
- 保持工具调用、session、events 行为不变

## 范围外
- API 选择 agent
- 多 agent 合并
- 自动选择 agent
- agent 工具权限

## 实现步骤
1. 修改 `Agent` 初始化参数，允许传入 `AgentDefinition` 或 instructions。
2. 将原硬编码 `SYSTEM_PROMPT` 降级为 fallback。
3. 在 service 层加载 default agent。
4. 确保现有测试不用改大量断言。
5. 增加一个测试确认 prompt 中包含 agent instructions。

## 完成标准
- 默认运行路径实际使用定义层。
- 删除或修改默认定义会影响 prompt 构造。
- 现有工具调用测试通过。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- Agent 是否仍然只关心运行，不关心定义来源。
- fallback 是否清晰。
- 是否没有把读取器写进 agent 主循环深处。
