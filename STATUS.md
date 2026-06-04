# STATUS

## Current Status
- Phase: planning
- Task: TASK-092 内存虚拟文件系统暂存与打断回滚机制 (In-Memory VFS Staging & Cancellation Rollback) & TASK-093 统一工作区投影与沙箱安全校验 (Unified Workspace Staging & Sandbox Path Redirection)
- Gate: design / planning
- Allowed Now: review / plan
- Lane: Fast
- Blocked: None
- Next action: 讨论并实现写文件工具在内存 VFS 中的暂存与统一沙箱安全拦截（支持同步子 Agent 运行模式）。


## 读取规则
- `STATUS.md` 是当前唯一权威入口，先看这里再看路线图。
- 任务号不等于时间顺序；遇到临时插卡、收口卡或重构卡时，以当前任务正文和状态为准。
- 路线图只负责长期顺序，不能直接推导当前正在做哪一张卡。


## 遗留项
- 见 `specs/TASK-002.md`

## 近期记录

| Date | Event | Gate / Phase | Notes |
|------|-------|--------------|-------|
| 2026-06-04 | 智能体被打断排队机制与工具实时自动展开完成 | Verify / Review | 成功实现流式打断消息排队（Up/Down/Trash三向选项），工具在运行时自动展开显示发光呼吸灯，修复了打断时工具回复在DB快照中丢失的Bug，后端单测与集成测试100%通过。 |
| 2026-06-04 | TASK-091 归档 | Verify / Review | 成功实现多会话并行流式生成与状态隔离。重构 useWorkspace.ts 状态为 sessionStates 映射，利用 Vue Writable Computed 代理，在零改动 Vue 视图组件的前提下无缝支持并行；移除切换会话时的主动 stopStreaming 中止动作；重构 useRunStreaming.ts 使流式写入锁定目标会话数据桶，前端 Vite 编译 100% 成功。 |
| 2026-06-04 | TASK-088 归档 | Verify / Review | 成功实现命令行 `/fork` 与 `/fork <提问>` 会话分支派生。后端深拷贝消息快照及 Trace 流水（Runs, Events, ToolCalls）；前端 useWorkspace 编排拦截命令；侧边栏实现 DFS 嵌套树状结构渲染及连接线、⌥ Branch 徽章，70项单测与32项集成测试全绿，前端打包编译成功。 |
| 2026-06-03 | TASK-087 归档 | Verify / Review | 成功实现历史消息原地编辑与级联截断清理逻辑，包括后端 SessionService 级联物理删除、前端 MessageList inline Textarea 编辑器及流式重发，96项单测/32项集成测试全绿。 |
| 2026-06-03 | TASK-086 归档 | Verify / Review | 成功实现 LLM API 网络与临时服务错误自动回退重试，完成前端流式异常捕获、部分响应留存、以及顶配 glassmorphic 错误卡片与一键 Retry 触发器。 |
| 2026-06-02 | TASK-083/084/085 归档 | Verify / Review | 成功实现并行工具批次审批状态机与进度闭环、MessageList 模块化重构与审批 UX 升级、侧边栏项目文件夹快捷操作与聊天区顶部绑定栏净化，前端构建与测试 100% 绿灯。 |
| 2026-05-30 | 已完成任务卡归档 | — | 将 TASK-073/074/075/076/078/079/080/081/082 移入 `specs/done/`。 |
| 2026-05-30 | `TASK-076` 并发工具执行与流式进度流完美收口 | Verify / Review | 成功实现基于 `asyncio.gather` 与 `asyncio.Queue` 管道的流式进度并发广播，完成跨线程 `run_coroutine_threadsafe` 自愈通信，以及审批拦截时 Task 优雅 Cancel 安全手刹，前后端 Vue 3 呼吸动效完美打包编译，96 项单测全绿通过。 |
| 2026-05-30 | `TASK-082` 后端核心及周边链路风格收敛完成 | Verify / Review | 完成两轮风格大扫除：统一 execution/context/memory 核心层及 api/settings/tools 主链路所有文件的模块头注释与 docstring 模板，替换所有的“教学散文”；`ContextAssembler` 抽出工作区文本读取 helper；`black`、`ruff check`、96 项 unit/integration tests 全绿通过。 |
| 2026-05-30 | `TASK-081` 运行时边界拆解完成 | Verify / Review | 新增 RuntimeContextFactory / ChildAgentDispatcher / TraceQueryService，RunService 收窄为 façade；`core/types.py` 剥离运行时与工具结果类型；前端 `useWorkspace.ts` 拆为 5 个 workspace composable；`python3 -m unittest agent_prototype.tests.integration.test_agent_api`、unit tests、`python3 -m compileall agent_prototype`、`npm run build` 全通过。 |
| 2026-05-28 | 领域类型归位完成，api/dto/schemas.py 精简为纯 HTTP I/O 文件 | Verify / Review | 新建 model/types/agent.py、skills/types.py、execution/streaming/types.py。22 处非 API 层文件的 `from api.dto.schemas import` 已全部迁至对应低层模块。api/routes 与测试同步迁移。删除 schemas.py 中的 re-export 块。96 项测试全绿。 |
| 2026-05-27 | 整体架构极致重构解耦与九层模型边界清洗完成 | Verify / Review | 成功实现 L1-L8 层全解耦。L2 彻底无状态化，L3 桥接工具完全闭包回调化，L5-L8 循环依赖完全剥离，落地 L6 统一装配器 ContextAssembler，96 项单测全部绿灯通过。 |
| 2026-05-23 | 编写通用中间件地基与工具中间件包并验证 | Verify / Review | 跳过切片5，直接完成切片6。成功实现完全通用的 BaseMiddleware、MiddlewarePipeline 地基，并派生出首个工具特定的 SandboxMiddleware、ApprovalMiddleware 与 4 个单元测试，单测完美通过（81/83 Passed）。 |
| 2026-05-22 | 已完成任务卡归档 | — | 将 TASK-030/035/036/037/038/038-1/038-2/040/040b/041/071/072a/072b 移入 `specs/done/`；SUPP-03/04 未完成保留原位。 |
| 2026-05-22 | 极精细镂空 SVG 图标与高内聚工具卡片重构 | Verify / Review | 成功手绘 9 个 1.5px 圆角镂空 SVG 图标，实现事件流按 `tool_call_id` 高度聚拢为单卡片，支持手风琴展开查看参数、耗时及响应，完美通过严格打包。 |
| 2026-05-21 | UI Premium 顶奢重构完成 | Verify / Review | 成功实现 820px 黄金视域消息列、右置不对称微光对话气泡、Spotlight 侧边栏浮雕会话卡片、以及随主题变色的半透明磨砂 Header，打包构建 100% 通过。 |
| 2026-05-21 | `TASK-072b` 与 UI 视觉动效升级收口 | Verify / Review | 成功实现 4 套极客深色主题、输入框毛玻璃拟态与 3D 聚焦悬浮发光轮廓、以及符合弹簧物理特性的消息上滑滑动动效，前端严格构建 `npm run build` 100% 通过。 |
| 2026-05-19 | `TASK-041` 收口 | Verify / Review | Agent 管理全链路完成：builtin agent 从 .md 文件加载（is_builtin 标记）、自定义 agent CRUD（POST/DELETE /agents）、前端 AgentManager 面板（新建/编辑/删除）、工具多选下拉（GET /tools）、dropdown 绑定真实后端数据替换 MOCK_AGENTS。 |
| 2026-05-18 | 子 Agent 面板 bug 修复 & code review | Verify / Review | 修复 save_partial_run 查错表、_global_futures 内存泄漏、子 Agent 未透传 RUN_MODEL；前端修复 AgentEvent 导入缺失、extractChildAgents 状态硬编码、localStorage 无限增长；子 Agent 最终输出支持 Markdown 渲染，formatContent 提取为共享工具；面板滚动问题修复。 |
| 2026-05-17 | `TASK-040` 收口 | Verify / Review | 多 Agent 子任务模型完成：parent_run_id 字段+migration、create_child_run/get_children_runs、spawn_child_agent 工具、build_run_registry 动态注册、5个单测全通过。 |
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
