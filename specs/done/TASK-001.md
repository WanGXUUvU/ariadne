# TASK-001

## Goal
完成第一个工具调用闭环，让 `agent.py` 支持 `tool_calls -> 工具执行 -> tool 回填 -> 再次请求模型 -> final reply`。

## In Scope
- `agent.py` 增加工具调用控制流
- `llm_client.py` 返回完整 assistant message
- `tools.py` 提供最小可执行工具
- `tests` 覆盖工具调用和最终回复两段流程

## Out of Scope
- 多工具编排
- 多 Agent
- RAG
- 持久化数据库设计

## Done when
- 一次请求能先触发工具调用，再得到最终回复
- 测试能覆盖工具调用分支和最终回复分支
- 当前任务卡有明确的 Verify 和 Review 结果
