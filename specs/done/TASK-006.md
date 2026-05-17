# TASK-006 - Agent 定义基础

## 目标
建立项目自己的 Agent 定义基础，让 agent 从 Python 内存对象变成可读、可维护、可扩展的产品配置。

## 产品层
Agent Core

## 背景
开源 agent 产品通常先有一个核心定义层，再让 UI、CLI、API 去消费这个定义层。OpenHands 把 SDK 作为 source of truth，接口层复用同一套对象；AutoGen Studio 把 agents、workflows、sessions 分层；LangGraph 则把 control 和 durability 放在 runtime 侧。我们先做最小定义层，不做多 agent 编排。

## 范围内
- 设计 `AgentDefinition` 的最小字段
- 提供一个默认 agent 定义，作为系统启动时的 fallback
- 让定义层能被后续的 registry、loader、UI 直接消费
- 保留现有 `/run`、`/reset`、session、events 行为不变

## 范围外
- 多 agent 编排
- 自动路由 agent
- Agent 定义 UI
- 插件系统
- MCP
- 工具权限约束

## 实现步骤
1. 定义 `AgentDefinition` 的字段和默认值。
2. 选择最小持久化方式，优先复用现有 SQLite 基础。
3. 生成一个默认 agent 定义，供服务层 fallback 使用。
4. 保持 agent 主循环不变，先只接通定义层。
5. 为默认定义补单元测试。

## 完成标准
- 仓库里存在清晰的 agent 定义层。
- 默认 agent 定义可以被人直接读懂。
- 现有测试仍然通过。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- 定义层是否和未来 registry、loader、UI 兼容。
- 是否没有提前改 runtime。
- 默认定义是否足够小，适合后续渐进加载。
