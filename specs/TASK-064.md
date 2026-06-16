# TASK-064 - Responses API Adapter 实现

## 目标
在不删除现有 Chat Completions adapter 的前提下，新增 Responses API adapter。

## 产品层
Model Adapter

## 背景
当前代码可以继续保留，但长期要向官方更推荐的 Responses API 迁移。本任务只新增 adapter，不切默认路径。

## 范围内
- 新建 Responses adapter 类
- 映射 messages / instructions / tools
- 映射 tool call 和 tool output
- 支持通过配置选择 adapter
- 保留旧 adapter 可回退

## 范围外
- 全量切换默认模型协议
- streaming
- 删除旧代码

## 实现步骤
1. 先整理当前 `llm_client.py` 的输入输出。
2. 定义统一 adapter interface。
3. 新增 `responses_adapter.py`。
4. 写 mock 测试，不依赖真实网络。
5. 手动测试真实调用放到可选验证。

## 完成标准
- 两个 adapter 可以共存。
- Agent Runtime 不关心底层协议。
- 测试不需要真实 API Key。

## 验证
- `python3 -m unittest backend.tests.test_agent -v`
- 可选：有 API Key 时手动跑一次真实 Responses 调用。

## Review 检查点
- 是否避免一次性重写 agent 主循环。
- tool call 映射是否清楚。
- 旧 adapter 是否仍可运行。

