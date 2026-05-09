# BUILD_PLAN

## 规划原则

这份路线图只负责说明长期方向；日常实现仍然只看 `STATUS.md` 和当前任务卡。

## 产品目标

同一仓库，共享内核，打造两个独立产品：

### 产品 A — 聊天助理（Chat Assistant）
目标用户：需要对话式 AI 助理的普通用户。
核心体验：Web UI 聊天 + streaming 输出 + 工具调用 + 会话管理 + Skill 扩展。
参考产品：Claude.ai、ChatGPT。

### 产品 B — 编码产品（Coding Agent）
目标用户：开发者，在项目目录里使用 CLI 或 UI 辅助编码。
核心体验：CLI 入口 + 文件工作区 + diff/review 审批 + 权限控制。
参考产品：Claude Code、GitHub Copilot Workspace。

## 仓库结构

```
agent_prototype/
  core/           # 共享 — AgentDefinition, Schema, ToolTypes
  runtime/        # 共享 — Agent 执行器, LLM Client, Tool Registry
  storage/        # 共享 — Session, Trace, DB
  skills/         # 共享 — Skill 加载/索引/启用
  api/            # 共享 HTTP API
  cli/            # 编码产品入口（TASK-058）
  agents_defs/    # 两个产品的 Agent 定义
    assistant.yaml  # 聊天助理
    coding.yaml     # 编码产品
  tools_defs/
    echo.py         # 通用
    web_search.py   # 聊天助理专用（TASK-056）
    fs_read.py      # 编码专用
    fs_write.py     # 编码专用
    shell_exec.py   # 编码专用（待实现）
frontend/         # 聊天助理 Web UI
```

参考能力面：
- OpenAI Codex Skills：`SKILL.md`、渐进加载、显式/隐式调用、可附带脚本和资源。
- OpenAI Codex Plugins：插件作为分发单位，官方结构以 `.codex-plugin/plugin.json` 为入口，根目录可包含 `skills/`、`.mcp.json`、`.app.json`、`hooks/`、`assets/`。
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

状态：已完成

任务：
- `TASK-006` Agent 定义基础 ✅
- `TASK-007` Agent 定义读取器 ✅
- `TASK-008` 将 Agent 定义注入 Agent Runtime ✅
- `TASK-009` 显式选择 Agent ✅

## M3 - Tool Registry 与工具约束

状态：已完成

任务：
- `TASK-010` 统一 Tool Registry ✅
- `TASK-011` Agent 允许工具列表 ✅
- `TASK-012` 工具错误事件 ✅
- `TASK-013` 工具结果规范化 ✅

## M4 - Session 产品层

状态：已完成

任务：
- `TASK-014` Session 元数据 ✅
- `TASK-015` Session 列表和读取接口 ✅
- `TASK-016` Trace 回放接口 ✅

## M5 - Agent 扩展管理

状态：已完成

任务：
- `TASK-017` 扩展索引元数据 ✅
- `TASK-018` 渐进式扩展加载 ✅
- `TASK-019` 扩展启用和禁用配置 ✅
- `TASK-020` 会话上下文压缩 ✅

## M6 - 聊天助理 MVP ← 当前阶段

状态：进行中

目标：
打通聊天助理的完整用户闭环：先把当前已有后端能力集中接入一个前端工作台，再进入 streaming 和专属 agent 定义阶段。

任务（按执行顺序，数字即顺序）：
- `TASK-021` API 输出整理 ✅
- `TASK-022` 前端规划任务卡 ✅
- `TASK-023` 新建 Session 接口 ✅
- `TASK-024` 现有后端能力前端整合 【聊天助理：chat + sessions + trace + skills + compact + reset】
- `TASK-025` 已并入 `TASK-024`
- `TASK-028` 模型适配层接口 【共享 — 重构模型调用层，为 Streaming 做准备】
- `TASK-049` Streaming 后端 SSE 【共享 — 提前到此阶段】
- `TASK-052` Streaming 前端接入 【聊天助理】
- `TASK-053` Chat Assistant Agent 定义 【聊天助理】
- `TASK-054` 消息 Markdown / 代码块渲染 【聊天助理】

## M7 - 聊天助理完善

状态：计划中

目标：
补齐会话管理、命令系统、搜索工具、Memory、多 Agent 等助理产品核心能力。

任务（按执行顺序，数字即顺序）：
- `TASK-035` Slash Command 解析器 【共享】
- `TASK-036` Session fork / resume / new 【共享】
- `TASK-038` 运行配置与人格配置 【共享】
- `TASK-039` 后台任务表 【共享】
- `TASK-040` 停止和取消运行 【共享 — 依赖 TASK-039】
- `TASK-041` Token 与上下文使用统计 【共享】
- `TASK-046` Skill / Plugin / Agent 管理界面 【聊天助理】
- `TASK-050` Memory 层 【聊天助理】
- `TASK-051` 多 Agent 子任务模型 【聊天助理】
- `TASK-055` Session 重命名与删除 【聊天助理】
- `TASK-056` Web 搜索工具 【聊天助理】

## M8 - 编码产品 MVP

状态：计划中

目标：
在聊天助理 MVP 完成后，启动编码产品主线：CLI 入口 + 文件工作区 + diff/review 审批闭环。

任务（按执行顺序，数字即顺序）：
- `TASK-030` 权限配置数据结构 【编码产品 — 权限基础】
- `TASK-031` 工具审批流程 【编码产品 — 依赖 TASK-030】
- `TASK-032` 文件工作区只读工具 【编码产品】
- `TASK-033` 文件写入草案与 diff 【编码产品 — 依赖 TASK-032】
- `TASK-034` 审批与文件操作审计日志 【编码产品 — 依赖 TASK-031 + TASK-032】
- `TASK-043` Git diff 读取能力 【编码产品】
- `TASK-044` Review 模式 【编码产品 — 依赖 TASK-043】
- `TASK-045` Verify 命令运行器 【编码产品】
- `TASK-047` 权限审批 UI 【编码产品 — 依赖 TASK-031】
- `TASK-057` Coding Agent 定义 【编码产品 — 引用 TASK-032/033 的工具名】
- `TASK-058` CLI 入口 【编码产品】
- `TASK-059` Diff Viewer UI 面板 【编码产品 — 依赖 TASK-033】

## M9 - 平台扩展（共享）

状态：计划中

目标：
为 MCP、插件打包、多模型协议迁移做准备，不提前引入重复杂度。

任务：
- `TASK-026` MCP 边界设计 【共享】
- `TASK-027` Plugin 包格式 【共享】
- `TASK-029` Responses API 迁移计划 【共享】
- `TASK-037` Skill 草稿创建流程 【共享】
- `TASK-042` Debug config 与 health 接口 【共享】
- `TASK-048` Responses API Adapter 实现 【共享】
