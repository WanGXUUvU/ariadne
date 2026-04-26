# TASK-026 - 模型适配层接口

## 目标
把模型调用封装成可替换 adapter，为未来从 Chat Completions 迁移到 Responses API 做准备。

## 产品层
会话运行层（Session Runtime）

## 范围内
- 定义模型 adapter 接口
- 当前 `llm_client.py` 作为 chat-completions adapter
- `Agent` 依赖 adapter 接口而不是具体函数
- 测试覆盖当前 adapter 行为

## 范围外
- 立即迁移 Responses API
- 多模型路由
- 成本统计
- 流式输出

## 完成标准
- 模型 API 细节从 agent 主循环中隔离
- 当前功能不回退
- 后续迁移 Responses API 不需要重写整个 Agent

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`
