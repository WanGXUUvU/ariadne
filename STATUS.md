# STATUS

## Current Status
- Phase: implementation
- Task: specs/TASK-025.md
- Gate: implementation
- Allowed Now: implementation, verify
- Lane: Fast
- Blocked: None
- Next action: 按 B1→B2→B3→B4 顺序逐个修复后端 Bug，前端部分已自动修完。


## 遗留项
- 见 `specs/TASK-002.md`

## History
| Date | Task | Gate Passed | Notes |
|------|------|-------------|-------|
| 2026-04-24 | 完成第一个工具调用闭环 | Verify / Review | 已跑通 `tool_calls -> tool -> final`，并用 `curl` 验证。 |
| 2026-04-24 | 规划会话隔离任务 | implementation | 已确认当前原型需要按 `session_id` 隔离状态，进入下一阶段。 |
| 2026-04-24 | 实现会话隔离与重置 | implementation | 已改为按 `session_id` 读写内存会话状态，并提供 `/reset`。 |
| 2026-04-24 | 手动验证会话隔离 | Verify | `A` 可续上下文，`B` 独立，`/reset` 后 `A` 重新开始。 |
| 2026-04-24 | `TASK-002` 功能收口 | Review | 会话隔离与重置功能完成，测试按当前安排延期。 |
| 2026-04-24 | 回归验证失败 | Verify | `unittest` 运行失败，`AgentInput` 还缺 `session_id`，测试未同步。 |
| 2026-04-24 | 回归验证通过 | Verify | `python3 -m unittest agent_prototype.tests.test_agent -v` 通过。 |
| 2026-04-24 | 创建下一张任务卡 | planning | 新增 `specs/TASK-003.md`，聚焦会话持久化。 |
| 2026-04-24 | 确认存储方案 | planning | `TASK-003` 先走 SQLite，不上更重的数据库。 |
| 2026-04-26 | 开始接通 SQLite 链路 | implementation | 已有 `db.py`、`models.py`、`session_store.py`、`services.py`，下一步是修正接口引用并初始化表。 |
| 2026-04-26 | `TASK-003` 功能完成 | Review | SQLite 会话持久化链路已跑通，功能收口。 |
| 2026-04-26 | 创建下一张任务卡 | planning | 新增 `specs/TASK-004.md`，聚焦 SQLite 迁移与 Alembic。 |
| 2026-04-26 | `TASK-004` 验证完成 | Verify | Alembic baseline migration 已补齐并通过 `upgrade head` / `current` 验证。 |
| 2026-04-26 | `TASK-004` 收口 | Review | `session_records` 已完成 Alembic 接管，迁移流程可用。 |
| 2026-04-26 | 创建下一张任务卡 | planning | 新增 `specs/TASK-005.md`，聚焦结构化执行轨迹输出。 |
| 2026-04-26 | `TASK-005` 验证完成 | Verify | `AgentEvent` 结构化输出与测试已跑通，`/run` 返回稳定轨迹。 |
| 2026-04-26 | `TASK-005` 收口 | Review | 结构化执行轨迹已完成，主线回到 Prompt/Skill 与工具编排。 |
| 2026-04-26 | 创建下一张任务卡 | planning | 新增 `specs/TASK-006.md`，聚焦 Prompt/Skill 体系 v1。 |
| 2026-04-26 | 仓库体检 | Review | 发现 `tools.py` 冲突标记导致测试无法导入，且 `llm_client.py` 存在硬编码 API Key，需先处理。 |
| 2026-04-26 | 修复导入阻塞 | Verify | `tools.py` 的 merge conflict 标记已清除，`python3 -m unittest agent_prototype.tests.test_agent -v` 通过。 |
| 2026-04-27 | 重新分解 `TASK-006` | planning | `TASK-006` 已从内存 prompt 过渡为 Agent 核心定义路线，并为后续 skill / plugin 扩展预留结构。 |
| 2026-04-27 | 建立产品规划与任务卡体系 | 实现审批 | 新增 `SPEC.md`、`DECISIONS.md`、`BUILD_PLAN.md`，删除旧 `TASK-006` 并重建 `TASK-006` 到 `TASK-027`。 |
| 2026-04-27 | 切换为轻量流程 | 规划 | 保留已预建任务卡和路线图，但日常执行只推进当前任务卡，路线文档仅在范围变化时读取。 |
| 2026-04-27 | 精简流程文档 | 规划 | 删除完整流程遗留的 `SPEC.md` 和 `DECISIONS.md`，轻量流程保留 `STATUS.md`、任务卡和 `BUILD_PLAN.md` 路线图。 |
| 2026-04-27 | 扩展 Codex 类产品路线 | 规划 | 基于 Codex 官方 Skills / Plugins / CLI 能力面，细化 `TASK-006` 到 `TASK-027`，新增 `TASK-028` 到 `TASK-051`。 |
| 2026-04-27 | 校正产品方向 | 规划 | 结合开源 agent 产品的架构，对当前阶段切换为 Agent 核心定义 + Skill / Plugin 扩展路线。 |
| 2026-04-27 | 路线审查完成 | Review | 任务卡主线整体合理，少量残留语义仍需统一，重点关注 plugin 是否要承载 agents、以及 skill 术语是否继续保留。 |
| 2026-04-27 | `TASK-006` 功能完成 | Verify / Review | Agent 定义层已接入 runtime，默认定义与 SQLite store 已打通，单测通过。 |
| 2026-04-27 | `TASK-007` 功能完成 | Verify / Review | 默认 agent 定义读取器已接入数据库读取与内存回退，单测通过。 |
| 2026-04-27 | `TASK-008` 功能完成 | Verify / Review | Agent 定义已注入 runtime，默认运行路径使用定义层，单测通过。 |
| 2026-04-27 | `TASK-009` 功能完成 | Verify / Review | Agent 输入已支持显式 agent_name，默认回退与未知 agent 错误路径已验证。 |
| 2026-04-28 | `TASK-010` 功能完成 | Verify / Review | Tool Registry 已统一注册本地工具，schema 暴露与执行链路已通过测试。 |
| 2026-04-28 | `TASK-011` 功能完成 | Verify / Review | Skill 工具允许列表已串到 runtime，默认 skill 仍可用 echo_tool，禁止工具会被拦截。 |
| 2026-04-28 | `TASK-012` 验证完成 | Verify | 工具错误已转成结构化 `tool_error` 事件，未知工具、参数错误、运行异常测试通过。 |
| 2026-04-28 | `TASK-013` 验证完成 | Verify | 工具结果已统一为 `ToolResult`，成功和失败路径都通过测试。 |
| 2026-04-28 | 模块结构整理完成 | Review | 将 `agent_prototype/` 按 api/core/runtime/storage/tools_defs 分层，旧入口路径已清理，新入口可从 `agent_prototype.api.app` 启动。 |
| 2026-04-28 | `TASK-014` 验证完成 | Verify | Session 元数据已接入 `session_records`，创建/更新时间、最近 agent、消息数和回复预览都通过测试。 |
| 2026-04-29 | `TASK-014` 收口 | Review | Session 元数据已完成，进入 Session 列表与读取接口阶段。 |
| 2026-04-29 | `TASK-015` 验证完成 | Verify | Session 列表、详情和 404 路径已补齐，API 测试通过。 |
| 2026-04-29 | `TASK-015` 收口 | Review | Session API 已具备列表与读取能力，下一步进入 Trace 回放接口。 |
| 2026-05-02 | `TASK-016` 验证完成 | Verify | Trace 落库、`GET /sessions/{session_id}/trace`、`run_id` 过滤和顺序测试通过。 |
| 2026-05-02 | `TASK-016` 收口 | Review | Trace 回放接口已打通，并补齐 Alembic 迁移。 |
| 2026-05-02 | 补充教练式拆任务方法 | planning | `AGENTS.md` 新增 6 行拆解模板和按层分析规则，后续任务先拆再写。 |
| 2026-05-02 | 强化大代码量教学节奏 | planning | `AGENTS.md` 补充“只看当前任务主链路、先定义任务再画链路再按层读”的规则，后续新会话默认按这个节奏带。 |
| 2026-05-02 | 切换到下一张任务卡 | planning | 当前任务切到 `TASK-017`，进入 Skill 索引元数据阶段。 |
| 2026-05-02 | 拆解 `TASK-017` 主链路 | planning | 确认先做 skill 索引最小闭环：测试夹具 -> metadata schema -> loader 列表函数 -> API/测试。 |
| 2026-05-02 | 升级教练闭环 | planning | `AGENTS.md` 增加“讲完即提问、复述检查、答偏先纠偏再推进”的规则，后续默认按教练闭环带学。 |
| 2026-05-02 | 强制分层串行实现 | planning | `AGENTS.md` 补充“进入实现后一次只推进一层，不一次性给出多层完整代码”的规则。 |
| 2026-05-02 | `TASK-017` 验证完成 | Verify | Skill metadata schema、loader、`GET /skills` 和坏 skill 容错测试已补齐，`python3 -m unittest agent_prototype.tests.test_agent -v` 通过。 |
| 2026-05-02 | `TASK-017` 收口 | Review | 接受当前 skill 扫描实现，切到下一张任务卡 `TASK-018`。 |
| 2026-05-02 | 切换到下一张任务卡 | planning | 当前任务切到 `TASK-018`，进入渐进式 Skill 加载阶段。 |
| 2026-05-03 | `TASK-018` 验证完成 | Verify | 已接入 skill catalog prompt、`skill_name` 显式全文加载和对应 API 测试，`python3 -m unittest agent_prototype.tests.test_agent -v` 通过。 |
| 2026-05-03 | `TASK-018` 收口 | Review | 接受当前渐进式 Skill 加载最小闭环，切到下一张任务卡 `TASK-019`。 |
| 2026-05-03 | 切换到下一张任务卡 | planning | 当前任务切到 `TASK-019`，进入 Skill 启用和禁用配置阶段。 |
| 2026-05-05 | `TASK-019` 验证完成 | Verify | 已补充 skill disabled 配置、enable/disable API、disabled skill 运行时拦截测试，`python3 -m unittest agent_prototype.tests.test_agent -v` 通过。 |
| 2026-05-05 | 重写 `TASK-020` 拆解 | planning | 按 OpenAI/Codex compact 机制重写任务卡，明确“主动 compact + 自动 compact + 共享核心 + 第一版规则摘要”主线。 |
| 2026-05-05 | 调整 `TASK-020` 路线 | planning | 将 `TASK-020` 改为“LLM 压缩中段核心历史 + 保留前锚点与最近原文”的标准 compact 方案。 |
| 2026-05-05 | `TASK-020` 验证完成 | Verify | 手动 `/compact` 与 `/run` 自动 compact 测试已通过，LLM 压缩中段历史链路已打通。 |
| 2026-05-05 | `TASK-020` 收口 | Review | 接受当前 compact 最小闭环实现，下一步切到 `TASK-021` 做 `/run` 输出整理。 |
| 2026-05-05 | 切换到下一张任务卡 | planning | 当前任务切到 `TASK-021`，进入 `/run` 响应结构整理阶段。 |
| 2026-05-06 | 拆解 `TASK-021` 主链路 | planning | 已确认当前 `/run` 已有 `reply/state/events/metadata`，并决定保留完整 `state`，下一步统一错误响应与测试。 |
| 2026-05-06 | `TASK-021` 收口 | Review | 统一业务错误响应为顶层 `error`，相关测试通过。 |
| 2026-05-07 | `TASK-023` 验证完成 | Verify / Review | `POST /sessions` 已打通，空 session 可创建并出现在列表中，测试通过，Review 通过。 |
| 2026-05-07 | 双产品路线规划 | planning | 确定同仓库共享内核方案，新增 TASK-052～059，BUILD_PLAN 重组为 M6～M9。 |
| 2026-05-07 | 切换到下一张任务卡 | planning | 当前任务切到 `TASK-024` Web UI 基础壳。 |
| 2026-05-07 | 同步路线文档冲突 | planning | 已修正 `BUILD_PLAN` 中 `TASK-023` 状态、统一 `TASK-058` CLI 路径到 `agent_prototype/cli/main.py`，并将 `TASK-053` 的默认工具描述改为不提前引用未实现的 `web_search`。 |
| 2026-05-07 | 合并前端任务卡 | planning | 按“现有后端能力一次前端整合”的方向，将 `TASK-025` 并入 `TASK-024`，并把 `TASK-024` 扩展为 chat、sessions、trace、skills、compact、reset 的统一工作台任务卡。 |
| 2026-05-06 | `TASK-021` 收口 | Review | 确认 `/run` 继续保留完整 `state`，并将顶层 `error` 确认为当前统一业务错误响应格式，任务完成。 |
| 2026-05-06 | 删除任务卡 | planning | 删除旧 `TASK-022` 最小 CLI 入口任务卡。 |
| 2026-05-06 | 调整任务卡编号 | planning | 将前端规划任务卡改回 `TASK-022`，并新建 `TASK-023` 专门承载“新建 session 接口”。 |
| 2026-05-06 | 拆解 `TASK-022` 主链路 | planning | 先围绕 Chat / Sessions / Trace 三页梳理最小前端范围、现有 API 对齐情况与缺口，再决定后续 UI 任务卡。 |
| 2026-05-06 | 确认 `TASK-022` API 缺口 | planning | 已确认“创建新 session” 需要独立接口，不再只依赖前端自己生成 `session_id` 后首次调用 `/run`；缺口拆到 `TASK-023`。 |
| 2026-05-06 | `TASK-022` 收口 | Review | 已确认第一版前端范围为 Chat / Sessions / Trace，现有 API 基本够用，唯独缺少独立 `POST /sessions`，已拆到 `TASK-023`。 |
| 2026-05-06 | 开始 `TASK-023` | planning | 已按 `schema -> route -> service -> test` 打通独立新建会话主链路。 |
| 2026-05-06 | `TASK-023` 验证完成 | Verify | `POST /sessions` 已可创建空白会话、返回 `SessionSummary`、出现在 `GET /sessions` 中，`python3 -m unittest agent_prototype.tests.test_agent -v` 通过。 |
| 2026-05-06 | 重排后续任务卡 | planning | 将 `Web UI 基础壳` 和 `Trace 时间线面板` 前移为 `TASK-024`、`TASK-025`；原 `TASK-024` 到 `TASK-043` 顺延两位，路线图同步为“先前端闭环，再平台边界”。 |
| 2026-05-07 | `TASK-024` 第一阶段 | implementation | 已建立 `useWorkspace` 核心状态层，接入 `GlobalNav` 全局侧边栏和 `TopControlBar` 顶部控制区（含 Agent 选择、Compact、Reset），完成三栏大布局壳子搭建与技能库 Mock 页面入口。 |
| 2026-05-07 | `TASK-024` 视觉重构 | implementation | 彻底推翻初版 UI，完成 Linear/Vercel 风格的极简极客暗色主题重构（Monolithic App Shell、等宽字体、无气泡对话流、1px网格系统）。 |
| 2026-05-07 | `TASK-024` 前端全链路闭环 | Verify | 完成 `MessageComposer` 额度监控与 IME 处理，完成 `MessageList` 的 Compact 骨架屏与系统提示块渲染，修复 setup 致命错误，所有现有后端能力 100% 映射到 UI。 |
| 2026-05-07 | `TASK-024` (含 `TASK-025`) 收口 | Review | 单页工作台已达到预期，Session/Chat/Trace/Skill/Compact 五大核心功能彻底贯通，体验拉满。 |
| 2026-05-07 | 切换到下一张任务卡 | planning | 进入 MCP 架构阶段，开始推进 `TASK-026` MCP 边界设计。 |
