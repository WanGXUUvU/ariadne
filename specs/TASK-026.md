# TASK-026 - 模型适配层接口

## 目标
把模型调用从 Agent Runtime 中抽象出来，为 Chat Completions、Responses API 和未来其他模型供应商共存做准备。

## 产品层
Model Adapter

## 范围内
- 定义统一 `ModelAdapter` interface
- 当前 OpenAI Chat Completions 调用实现为一个 adapter
- Agent 只依赖 interface
- 测试中可以 mock adapter

## 范围外
- 立刻迁移 Responses API
- 多供应商 UI
- streaming

## 实现步骤
1. 审查当前 `llm_client.py`。
2. 定义输入对象：messages、tools、instructions、model config。
3. 定义输出对象：assistant message、tool calls、usage。
4. 把现有调用包成 `ChatCompletionsAdapter`。
5. 修改 Agent 通过 adapter 调用模型。
6. 更新测试使用 fake adapter。

## 完成标准
- Agent 不直接知道 OpenAI SDK 细节。
- 旧模型调用行为不变。
- 后续新增 Responses adapter 不需要重写 Agent。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- interface 是否贴近现有需求。
- 是否避免过度抽象。
- fake adapter 是否让测试更稳定。

