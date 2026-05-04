# BUILD_PLAN

## 规划原则

这份路线图只负责说明长期方向；日常实现仍然只看 `STATUS.md` 和当前任务卡。

我们的目标不是一次性重写成 Codex，而是在现有 FastAPI + Agent Runtime + SQLite + trace 的基础上，一层一层补齐产品能力：

- 先把 Agent 核心定义产品化：Agent Definition、Registry、Loader、Tool Registry。
- 再把运行过程产品化：Session、Trace、API、CLI。
- 再补齐 Codex 类产品的关键能力：权限、文件工作区、命令控制、后台任务、Review、插件、UI。
- 最后再做模型协议升级：Responses API、streaming、memory、多 agent。

参考能力面：
- OpenAI Codex Skills：`SKILL.md`、渐进加载、显式/隐式调用、可附带脚本和资源。
- OpenAI Codex Plugins：插件作为分发单位，插件内可包含 skills、MCP、app 配置和 assets。
- OpenAI Codex CLI：slash commands、权限、diff/review、session fork/resume、model/personality、MCP、plugins、status/debug。

## M1 - 稳定 Agent Runtime

状态：已完成

已完成：
- 工具调用闭环
- 会话隔离
- SQLite 持久化
- Alembic 迁移基线
- 结构化执行事件

## M2 - Agent 核心定义

状态：当前阶段

目标：
从硬编码 prompt 行为，迁移到可持久化、可选择的 Agent 定义。这里先做最小可用，不做多 agent 编排。

任务：
- `TASK-006` Agent 定义基础
- `TASK-007` Agent 定义读取器
- `TASK-008` 将 Agent 定义注入 Agent Runtime
- `TASK-009` 显式选择 Agent

## M3 - Tool Registry 与工具约束

状态：计划中

目标：
让工具具备产品级基础能力：可发现、可注册、可被 Agent 定义约束，并且可追踪。

任务：
- `TASK-010` 统一 Tool Registry
- `TASK-011` Agent 允许工具列表
- `TASK-012` 工具错误事件
- `TASK-013` 工具结果规范化

## M4 - Session 产品层

状态：计划中

目标：
把 session 存储从隐藏持久化能力，推进为用户可感知的产品能力。

任务：
- `TASK-014` Session 元数据
- `TASK-015` Session 列表和读取接口
- `TASK-016` Trace 回放接口

## M5 - Agent 扩展管理

状态：计划中

目标：
支持很多 agent 扩展同时存在，但不一次性把所有内容塞进上下文，向产品化的渐进式加载方式靠拢。

任务：
- `TASK-017` 扩展索引元数据
- `TASK-018` 渐进式扩展加载
- `TASK-019` 扩展启用和禁用配置
- `TASK-020` 会话上下文压缩

## M6 - 产品表面

状态：计划中

目标：
通过干净的用户入口暴露 Agent Runtime，让它不只是一个内部 API。

任务：
- `TASK-021` API 输出整理
- `TASK-022` 最小 CLI 入口
- `TASK-023` 前端规划任务卡

## M7 - 平台边界

状态：计划中

目标：
为 MCP、插件打包、多模型协议迁移做准备，但不提前引入重复杂度。

任务：
- `TASK-024` MCP 边界设计
- `TASK-025` Plugin 包格式
- `TASK-026` 模型适配层接口
- `TASK-027` Responses API 迁移计划

## M8 - 权限与工作区安全

状态：计划中

目标：
Codex 类产品必须能控制 agent 可以做什么，尤其是文件读写、命令执行、网络访问和人工审批。

任务：
- `TASK-028` 权限配置数据结构
- `TASK-029` 工具审批流程
- `TASK-030` 文件工作区只读工具
- `TASK-031` 文件写入草案与 diff
- `TASK-032` 审批与文件操作审计日志

## M9 - 会话控制与命令系统

状态：计划中

目标：
补齐 slash command、fork、resume、compact、model/personality 等交互控制能力。

优先级说明：
`TASK-020` 已前移处理长会话 compact。当前主链路在 skill 渐进加载之后，最容易暴露的问题就是 prompt 膨胀；上下文压缩比 skill 草稿创建更早影响可用性。

任务：
- `TASK-033` Slash Command 解析器
- `TASK-034` Session fork / resume / new
- `TASK-035` 扩展草稿创建流程
- `TASK-036` 运行配置与人格配置

## M10 - 后台任务与可观测性

状态：计划中

目标：
让 agent 的长任务可以被追踪、停止、查看状态，并能看到 token、耗时、错误等运行信息。

任务：
- `TASK-037` 后台任务表
- `TASK-038` 停止和取消运行
- `TASK-039` Token 与上下文使用统计
- `TASK-040` Debug config 与 health 接口

## M11 - Review 与 Git 工作流

状态：计划中

目标：
向 Codex 的 review/diff 能力靠拢，让 agent 不只是回答，还能围绕代码变更形成可审查闭环。

任务：
- `TASK-041` Git diff 读取能力
- `TASK-042` Review 模式
- `TASK-043` Verify 命令运行器

## M12 - 用户界面

状态：计划中

目标：
把 session、trace、agent、权限审批用 UI 暴露出来，形成真实产品体验。

任务：
- `TASK-044` Web UI 基础壳
- `TASK-045` Trace 时间线面板
- `TASK-046` Agent / Plugin 管理界面
- `TASK-047` 权限审批界面

## M13 - 模型协议与高级 Agent 能力

状态：计划中

目标：
在已有产品骨架稳定后，再迁移到更现代的模型协议和更强 agent 能力。

任务：
- `TASK-048` Responses API Adapter 实现
- `TASK-049` Streaming 事件输出
- `TASK-050` Memory 层
- `TASK-051` 多 Agent 子任务模型
