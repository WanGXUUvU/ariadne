# STATUS

## Current Status
- Phase: implementation
- Task: specs/TASK-037.md
- Gate: implementation
- Allowed Now: implementation
- Lane: Fast
- Blocked: None
- Next action: Stop 按钮前端实现（abort SSE + finalize 落库 + UI 标记）

## 读取规则
- `STATUS.md` 是当前唯一权威入口，先看这里再看路线图。
- 任务号不等于时间顺序；遇到临时插卡、收口卡或重构卡时，以当前任务正文和状态为准。
- 路线图只负责长期顺序，不能直接推导当前正在做哪一张卡。


## 遗留项
- 见 `specs/TASK-002.md`

## 近期记录

| Date | Event | Gate / Phase | Notes |
|------|-------|--------------|-------|
| 2026-05-14 | `TASK-028` 收口并切换到 `TASK-029` | Verify / Review | 前端完成 fetch+ReadableStream 解析 SSE，实现打字机效果及实时 Trace 面板，完善刷新后的历史统一渲染。 |
| 2026-05-15 | `TASK-036` 收口并切换到 `TASK-037` | Verify / Review | Session 重命名（画笔内联编辑）+ 删除前后端全链路完成，构建通过，手动验证 ok。 |
| 2026-05-14 | `TASK-035` 收口并切换到 `TASK-036` | Verify / Review | web_search 工具落地，接入 Tavily API，注册进 DEFAULT_TOOL_REGISTRY，assistant agent tool_names 已加入 web_search，全量测试通过。 |
| 2026-05-14 | `TASK-029` 收口并切换到 `TASK-035` | Verify / Review | ASSISTANT_AGENT_DEFINITION 常量落地，load_agent_definition 改为字典 fallback，现有测试全部通过。 |
| 2026-05-11 | `TASK-027` 收口并切换到 `TASK-028` | Verify / Review | streaming 后端全链路完成，SSE endpoint `/run/stream` 测试通过，顺手修复 `choices=[]` 空列表 IndexError。 |
| 2026-05-10 | 同步收紧 `TASK-027` / `TASK-028` | planning | 统一 SSE 语义事件契约，前端不再默认 token 级 delta。 |
| 2026-05-10 | 切换到 `TASK-027` | planning | `TASK-054` 暂停，先推进 streaming 事件输出主线。 |
| 2026-05-10 | 切换到 `TASK-054` | planning | `TASK-072` 已收口，进入 `MCP` 边界设计主线。 |
| 2026-05-10 | 补充卡 02 收口 | Verify / Review | `skill_loader.py` 已拆出 `skill_config.py`，`run_service.py` 收窄为预处理 / 执行 / 落库三段，`python3 -m unittest discover -s agent_prototype/tests -p 'test_*.py' -v` 通过。 |
| 2026-05-10 | 补充卡 01 收口 | Verify / Review | `agent_runtime.py` 已拆成 facade + helpers，runtime 单测和前端构建通过。 |
| 2026-05-10 | `TASK-070` 收口并切换到 `TASK-054` | Verify / Review | 路由入口拆分、应用层收窄完成，后续中心文件暂不继续拆。 |
| 2026-05-09 | `TASK-026` 收口并切换到 `TASK-070` | Verify / Review | 统一 `ModelAdapter` 与 `ChatCompletionsAdapter` 已落地，runtime / compact / run_service 已迁移。 |
| 2026-05-09 | 后端分层重构推进 | planning / Verify | `TASK-067` / `TASK-068` / `TASK-069` 依次完成重构、命名统一和测试拆分。 |
| 2026-05-09 | MCP / Plugin 路线校正 | planning | `TASK-054` / `TASK-057` 重新对齐官方结构，`mcp_servers.<id>` 与插件包格式开始分离。 |
| 2026-05-07 | 聊天助理 MVP 完成 | Verify / Review | `TASK-024`（含 `TASK-025`）收口，Session / Chat / Trace / Skill / Compact 前端工作台打通。 |

## 阶段里程碑

### M1 - M5 已完成
- 稳定 Agent Runtime
- Agent 核心定义
- Tool Registry 与工具约束
- Session 产品层
- Agent 扩展管理

### M6 - 聊天助理 MVP
- 当前阶段：进行中
- 已完成：`TASK-021`、`TASK-022`、`TASK-023`
- 已完成：`TASK-024` / `TASK-025` 前端整合
- 已完成：`TASK-026`、`TASK-027`、`TASK-028`
- 待推进：`TASK-029`、`TASK-030`

### M7 - M9
- `M7`：聊天助理完善，当前计划中
- `M8`：编码产品 MVP，当前计划中
- `M9`：平台扩展，共享能力后续推进

## 说明
- 历史区只保留最近与阶段级信息，避免把模型淹没在流水账里。
- 更早的逐条推进细节仍可从 git 历史或对应任务卡追溯。
