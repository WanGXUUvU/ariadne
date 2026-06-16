# TASK-009 - 显式选择 Agent

## 目标
允许 API 请求显式指定要使用的 Agent，例如 `agent_name="default"`。

## 产品层
API / Agent Core

## 范围内
- `AgentInput` 增加可选 `agent_name`
- service 层根据 `agent_name` 加载 agent
- 未传入时使用 default
- agent 不存在时返回清晰错误
- session 中记录本轮使用的 agent

## 范围外
- 自动选择 agent
- agent enable/disable
- 多 agent 组合
- UI agent 选择器

## 实现步骤
1. 修改 `AgentInput` schema，增加 `agent_name: str | None`。
2. 在 service 层确定 effective agent。
3. 加载失败时转成 API 可读错误。
4. 在 trace 或 response metadata 中记录 agent 名称。
5. 测试 default 路径和指定 agent 路径。

## 完成标准
- 请求不传 agent 时行为不变。
- 请求传入存在的 agent 时能使用对应 instructions。
- 请求传入不存在的 agent 时不会静默回退。

## 验证
- `python3 -m unittest backend.tests.test_agent -v`

## Review 检查点
- 错误是否清楚。
- session 是否记录了实际使用的 agent。
- API 是否保持向后兼容。
