# agent_prototype 迁移方案

> 目标：按九层能力模型重组目录，消除职责混杂，统一文件命名约定。  
> 原则：先建目录契约，不改业务逻辑，逐层搬迁，新旧共存直到全部完成。

---

## 一、迁移后完整目录树

```
agent_prototype/
│
├── model/                              # L1 模型层
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── chat_completions.py         ← infrastructure/llm/chat_completions_adapter.py
│   │   └── protocol.py                ← infrastructure/llm/model_adapter_protocol.py
│   ├── types/
│   │   ├── __init__.py
│   │   ├── domain.py              ← core/schemas.py  [LLM协议原语: ToolCall/ChatMessage/RiskLevel]
│   │   └── model_types.py             ← infrastructure/llm/model_types.py
│   └── __init__.py
│
├── prompt/                             # L2 提示词与指令层
│   ├── templates/
│   │   ├── system/
│   │   │   ├── assistant.md           ← infrastructure/agents/builtin/assistant.md
│   │   │   ├── default.md             ← infrastructure/agents/builtin/default.md
│   │   │   └── software_engineer.md   ← infrastructure/agents/builtin/software_engineer.md
│   │   └── task/
│   │       └── __init__.py            [new]
│   ├── strategies/
│   │   ├── __init__.py
│   │   ├── thinking.py                ← infrastructure/llm/thinking_styles.py
│   │   └── output_format.py           [new]
│   ├── schemas/
│   │   └── __init__.py                [new — 工具 function calling schema 定义]
│   ├── builder.py                     ← application/runtime/context/prompt_builder.py
│   └── __init__.py
│
├── tools/                              # L3 工具层
│   ├── registry.py                    ← infrastructure/tools/tool_registry.py
│   ├── protocol.py                    ← core/tool_types.py  [new — ITool 接口协议]
│   ├── builtin/
│   │   ├── filesystem/
│   │   │   ├── __init__.py
│   │   │   ├── fs_list.py             ← infrastructure/tools/builtin/fs_list.py
│   │   │   ├── fs_read.py             ← infrastructure/tools/builtin/fs_read.py
│   │   │   ├── fs_write.py            ← infrastructure/tools/builtin/fs_write.py
│   │   │   └── fs_search.py           ← infrastructure/tools/builtin/fs_search.py
│   │   ├── search/
│   │   │   ├── __init__.py
│   │   │   └── web_search.py          ← infrastructure/tools/builtin/web_search.py
│   │   ├── agent_bridge/
│   │   │   ├── __init__.py
│   │   │   ├── spawn_child_agent.py   ← infrastructure/tools/builtin/spawn_child_agent.py
│   │   │   ├── check_child_status.py  ← infrastructure/tools/builtin/check_child_status.py
│   │   │   └── wait_child_agent.py    ← infrastructure/tools/builtin/wait_child_agent.py
│   │   └── util/
│   │       ├── __init__.py
│   │       └── echo.py                ← infrastructure/tools/builtin/echo.py
│   ├── os/
│   │   ├── __init__.py                [new]
│   │   └── apple_script.py            ← infrastructure/os_proxy/apple_script.py  [macOS系统调用]
│   ├── mcp/
│   │   └── __init__.py                [new — MCP 协议接入，预留]
│   └── __init__.py
│
├── planning/                           # L4 规划层
│   ├── planner.py                     [new — 规划器协议与基类]
│   ├── replanner.py                   [new — 动态重规划]
│   ├── react/
│   │   ├── __init__.py
│   │   └── react_planner.py           [new — 从 agent_runtime 剥离]
│   ├── plan_execute/
│   │   └── __init__.py                [new]
│   ├── task_tree/
│   │   ├── __init__.py
│   │   └── task_node.py               [new]
│   └── __init__.py
│
├── memory/                             # L5 记忆层
│   ├── session/
│   │   ├── __init__.py
│   │   ├── service.py                 ← application/services/session_service.py
│   │   └── store.py                   ← infrastructure/database/repositories/session_store.py
│   ├── workspace/
│   │   ├── __init__.py
│   │   ├── service.py                 ← application/services/workspace_service.py
│   │   └── store.py                   ← infrastructure/database/repositories/workspace_store.py
│   ├── summary/
│   │   ├── __init__.py
│   │   └── service.py                 ← application/services/compact_service.py
│   ├── longterm/
│   │   └── __init__.py                [new — 长期偏好与项目知识，预留]
│   ├── vector/
│   │   └── __init__.py                [new — 向量检索接入，预留]
│   └── __init__.py
│
├── context/                            # L6 上下文工程层
│   ├── assembler.py                   [new — 上下文组装入口]
│   ├── compaction.py                  ← application/runtime/context/compaction.py
│   ├── retriever.py                   [new — 从记忆层检索相关片段]
│   ├── ranker.py                      [new — 上下文排序与优先级]
│   ├── injector.py                    [new — 注入时机与格式控制]
│   ├── skill_context.py               ← application/services/skill_context_service.py
│   └── __init__.py
│
├── security/                           # L7 权限与安全层
│   ├── approval/
│   │   ├── __init__.py
│   │   ├── middleware.py              ← application/runtime/middleware/approval.py
│   │   ├── service.py                 ← application/services/approval_service.py
│   │   └── store.py                   ← infrastructure/database/repositories/approval_store.py
│   ├── sandbox/
│   │   ├── __init__.py
│   │   └── middleware.py              ← application/runtime/middleware/sandbox.py
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── base.py                    ← application/runtime/middleware/base.py + core/middleware.py
│   ├── policy/
│   │   └── __init__.py                [new — 统一策略执行引擎，预留]
│   ├── audit/
│   │   └── __init__.py                [new — 审计日志，预留]
│   ├── policy.py                      [new — ApprovalPolicy/PermissionProfile/PROFILES/needs_approval]
│   ├── guard.py                       [new — 敏感内容检测，预留]
│   └── __init__.py
│
├── execution/                          # L8 执行与编排层
│   ├── runtime/
│   │   ├── __init__.py
│   │   ├── agent_runtime.py           ← application/runtime/agent_runtime.py
│   │   ├── agent_executor.py          ← application/runtime/executor.py
│   │   ├── tool_runner.py             ← application/runtime/tool_executor.py
│   │   ├── response_handler.py        ← application/runtime/response_handler.py
│   │   └── message_builder.py         ← application/runtime/message_builder.py
│   ├── streaming/
│   │   ├── __init__.py
│   │   ├── sse.py                     ← application/runtime/sse_utils.py
│   │   └── stream_run_session.py      ← application/services/run/stream_run_session.py
│   ├── persistence/
│   │   ├── __init__.py
│   │   ├── run_service.py             ← application/services/run/run_service.py
│   │   ├── run_persistence.py         ← application/services/run/run_persistence.py
│   │   └── run_context_builder.py     ← application/services/run/run_context_builder.py
│   ├── resume/
│   │   ├── __init__.py
│   │   └── resume_run_service.py      ← application/services/run/resume_run_service.py
│   ├── workflow/
│   │   └── __init__.py                [new — 状态机与工作流引擎，预留]
│   └── __init__.py
│
├── observation/                        # L9 评估与观测层
│   ├── tracer.py                      [new — Trace 采集与存储，对接 trace_routes]
│   ├── logger.py                      [new — 结构化日志]
│   ├── hooks/
│   │   ├── __init__.py
│   │   └── tool_run_observer.py       ← application/runtime/tool_run_observer.py
│   ├── metrics/
│   │   ├── __init__.py
│   │   ├── cost.py                    [new]
│   │   └── latency.py                 [new]
│   ├── eval/
│   │   └── __init__.py                [new — 离线评测与人工验收，预留]
│   └── __init__.py
│
├── infra/                              # 纯技术基础设施（无领域逻辑）
│   ├── db/
│   │   ├── __init__.py
│   │   ├── engine.py                  ← infrastructure/database/db.py
│   │   └── orm_models.py              ← infrastructure/database/models.py
│   ├── cache/
│   │   └── __init__.py                [new]
│   ├── config/
│   │   └── __init__.py                [new]
│   └── __init__.py
│
├── api/                                # HTTP 接口层（薄层，只做参数校验和分发）
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── agent_routes.py            ← interface/api/routes/agent_routes.py
│   │   ├── approval_routes.py         ← interface/api/routes/approval_routes.py
│   │   ├── compact_routes.py          ← interface/api/routes/compact_routes.py
│   │   ├── run_routes.py              ← interface/api/routes/run_routes.py
│   │   ├── session_routes.py          ← interface/api/routes/session_routes.py
│   │   ├── settings_routes.py         ← interface/api/routes/settings_routes.py
│   │   ├── skill_routes.py            ← interface/api/routes/skill_routes.py
│   │   ├── tool_routes.py             ← interface/api/routes/tool_routes.py
│   │   ├── trace_routes.py            ← interface/api/routes/trace_routes.py
│   │   ├── workspace_routes.py        ← interface/api/routes/workspace_routes.py
│   │   └── dependencies.py            ← interface/api/routes/common.py
│   ├── dto/
│   │   ├── __init__.py
│   │   └── schemas.py                 ← interface/dto/schemas.py
│   ├── app.py                         ← interface/api/app.py
│   └── __init__.py
│
├── agent/                              # Agent 定义与组装入口（跨层）
│   ├── definition.py                  ← core/agent_definition.py
│   ├── definition_service.py          ← application/services/agent_definition_service.py
│   ├── definition_store.py            ← infrastructure/database/repositories/agent_definition_store.py
│   ├── loader.py                      ← infrastructure/agents/agent_loader.py
│   ├── settings_service.py            ← application/services/settings_service.py
│   ├── settings_store.py              ← infrastructure/database/repositories/settings_store.py
│   ├── builtin/
│   │   └── __init__.py
│   └── __init__.py
│
├── skills/                             # Skill 子系统（跨层能力包）
│   ├── service.py                     ← application/services/skill_service.py
│   ├── loader.py                      ← infrastructure/skills/skill_loader.py
│   ├── config.py                      ← infrastructure/skills/skill_config.py
│   ├── builtin/
│   │   └── __init__.py                ← infrastructure/skills/builtin/__init__.py
│   └── __init__.py
│
├── tests/
│   ├── unit/
│   │   ├── model/
│   │   │   └── test_model_adapter.py  ← tests/test_model_adapter.py
│   │   ├── tools/
│   │   │   ├── test_tool_registry.py  ← tests/test_tool_registry.py
│   │   │   └── test_tool_pipeline.py  ← tests/test_tool_pipeline.py
│   │   ├── security/
│   │   │   ├── test_approval.py       ← tests/test_approval.py
│   │   │   ├── test_middleware.py     ← tests/test_middleware.py
│   │   │   └── test_permission.py     ← tests/test_permission.py
│   │   ├── execution/
│   │   │   ├── test_agent_runtime.py          ← tests/test_agent_runtime.py
│   │   │   ├── test_spawn_child_agent.py      ← tests/test_spawn_child_agent.py
│   │   │   └── test_parallel_child_agents.py  ← tests/test_parallel_child_agents.py
│   │   ├── memory/
│   │   │   ├── test_session_store.py  ← tests/test_session_store.py
│   │   │   └── test_workspace.py      ← tests/test_workspace.py
│   │   ├── planning/
│   │   │   └── __init__.py            [new]
│   │   └── observation/
│   │       └── __init__.py            [new]
│   ├── integration/
│   │   ├── test_agent_api.py                  ← tests/test_agent_api.py
│   │   ├── test_agent_definition_service.py   ← tests/test_agent_definition_service.py
│   │   └── test_skill_loader.py               ← tests/test_skill_loader.py
│   └── __init__.py
│
├── .agent/
│   └── skill-config.json
├── agent_session.db
├── dev.db
└── __init__.py
```

---

## 二、文件重命名对照表

### 命名规则

| 规则 | 说明 |
|---|---|
| 目录表达归属，文件名表达职责 | `memory/session/store.py` 而非 `memory/session/session_store.py` |
| 同类文件后缀统一 | 存储实现统一 `store.py`，服务统一 `service.py`，中间件统一 `middleware.py` |
| 不用 `_utils`、`common`、`base` 作为独立顶层文件 | 这类命名是职责未厘清的信号 |

### 完整重命名清单

**模型层 `model/adapters/`**

| 原文件名 | 新文件名 | 变更原因 |
|---|---|---|
| `chat_completions_adapter.py` | `chat_completions.py` | 目录已是 adapters/，后缀冗余 |
| `model_adapter_protocol.py` | `protocol.py` | 同上，且 model_ 前缀与目录重复 |
| `openai_adapter.py` | 已删除，不迁移 | 迁移前文件已缺失，功能与 chat_completions.py 完全重合 |
| `model_types.py` | 保持 `model_types.py` | 在 types/ 目录下语义仍清晰 |

**提示词层 `prompt/`**

| 原文件名 | 新文件名 | 变更原因 |
|---|---|---|
| `prompt_builder.py` | `builder.py` | 目录已是 prompt/，前缀冗余 |
| `thinking_styles.py` | `thinking.py` | 迁入 strategies/，_styles 后缀多余 |

**记忆层 `memory/`**

| 原文件名 | 新文件名 | 变更原因 |
|---|---|---|
| `session_service.py` | `service.py`（在 session/） | 目录已消歧义 |
| `session_store.py` | `store.py`（在 session/） | 同上 |
| `workspace_service.py` | `service.py`（在 workspace/） | 同上 |
| `workspace_store.py` | `store.py`（在 workspace/） | 同上 |
| `compact_service.py` | `service.py`（在 summary/） | 同上 |

**安全层 `security/`**

| 原文件名 | 新文件名 | 变更原因 |
|---|---|---|
| `approval.py`（middleware） | `middleware.py`（在 approval/） | 统一中间件命名约定 |
| `sandbox.py`（middleware） | `middleware.py`（在 sandbox/） | 同上 |
| `approval_service.py` | `service.py`（在 approval/） | 目录已消歧义 |
| `approval_store.py` | `store.py`（在 approval/） | 同上 |
| `settings_store.py` | `store.py`（在 agent/ 或 infra/） | 同上 |

**执行层 `execution/`**

| 原文件名 | 新文件名 | 变更原因 |
|---|---|---|
| `executor.py` | `agent_executor.py` | 区分 agent 级和 tool 级执行，消除歧义 |
| `tool_executor.py` | `tool_runner.py` | runner 更准确描述「运行单个工具」 |
| `sse_utils.py` | `sse.py`（在 streaming/） | _utils 是杂物箱命名，迁移后职责清晰无需后缀 |
| `stream_run_session.py` | 保持 | 名称语义清晰 |

**基础设施层 `infra/`**

| 原文件名 | 新文件名 | 变更原因 |
|---|---|---|
| `models.py`（ORM） | `orm_models.py` | 与业务层 models 区分，防止 import 混淆 |
| `db.py` | `engine.py` | 目录已是 db/，文件再叫 db.py 语义冗余；engine.py 明确描述「数据库引擎/连接池」职责 |

**Skill 子系统 `skills/`**

| 原文件名 | 新文件名 | 变更原因 |
|---|---|---|
| `skill_service.py` | `service.py` | 目录已消歧义 |
| `skill_loader.py` | `loader.py` | 同上 |
| `skill_config.py` | `config.py` | 同上 |

**API 层 `api/routes/`**

| 原文件名 | 新文件名 | 变更原因 |
|---|---|---|
| `common.py` | `dependencies.py` | 明确职责（FastAPI 依赖注入），消除「common 杂物箱」命名 |

**拼写修复（立即改，不依赖迁移进度）**

| 原文件名 | 新文件名 | 变更原因 |
|---|---|---|
| `setting_services.py` | `settings_service.py` | 复数 services 与全项目约定不一致 |
| `approval_toutes.py`（pycache） | 直接删除 | typo 遗留文件，不是源文件 |

**保持不变（命名已足够清晰）**

```
agent_runtime.py       message_builder.py     response_handler.py
run_persistence.py     run_context_builder.py  resume_run_service.py
compaction.py          web_search.py           apple_script.py
spawn_child_agent.py   check_child_status.py   wait_child_agent.py
fs_list.py             fs_read.py              fs_write.py / fs_search.py
tool_run_observer.py   agent_definition.py     agent_loader.py
```

---

## 三、已消灭的目录

迁移完成后，以下目录应完全消失：

| 消灭的目录 | 原因 | 内容去向 |
|---|---|---|
| `application/` | 大杂烩，同时含执行引擎和应用服务 | 按职责拆入 execution/ security/ context/ memory/ prompt/ |
| `infrastructure/agents/` | 领域内容（prompt 模板）放在了基础设施层 | → prompt/templates/system/ |
| `infrastructure/llm/` | 部分是模型适配（L1），部分是提示词策略（L2） | → model/adapters/ 和 prompt/strategies/ |
| `infrastructure/tools/` | 工具层独立成顶层 | → tools/ |
| `infrastructure/skills/` | Skill 子系统独立成顶层 | → skills/ |
| `infrastructure/database/` | 纯技术部分下沉，存储实现按层归位 | → infra/db/ 和各层 store.py |
| `infrastructure/os_proxy/` | 归入工具层或基础设施 | → tools/builtin/ 或 infra/ |
| `core/` | 内容已拆散 | definition→agent/, tool_types→tools/protocol.py, schemas→api/dto/, middleware→security/ |
| `interface/` | API 层独立成顶层 | → api/ |

---

## 四、层间依赖规则

```
observation/  →  只读 hook，可依赖任意层，禁止修改任何层的行为
execution/    →  编排者，通过协议调用各层，是唯一允许横向依赖的层
security/     →  横切关注点，依赖 infra/，禁止依赖 planning/ context/
planning/     →  依赖 prompt/ tools/（协议），禁止直接调用 execution/
context/      →  依赖 memory/ prompt/，禁止依赖 execution/ planning/
memory/       →  依赖 infra/db/，禁止依赖 context/ execution/
tools/        →  依赖 infra/，禁止依赖 planning/ execution/
prompt/       →  依赖 model/（类型），禁止依赖 execution/ memory/
model/        →  依赖 infra/，禁止依赖所有业务层
infra/        →  无业务依赖，只做技术适配
```

---

## 五、迁移执行顺序

迁移分八步，每步完成后运行全量测试再进入下一步。

### Step 0 — 建目录骨架（不移动任何文件）

```bash
# 建立所有新目录，每个目录写 __init__.py 和 README（说明职责契约）
mkdir -p model/{adapters,types}
mkdir -p prompt/{templates/{system,task},strategies,schemas}
mkdir -p tools/{builtin/{filesystem,search,agent_bridge,util},mcp}
mkdir -p planning/{react,plan_execute,task_tree}
mkdir -p memory/{session,workspace,summary,longterm,vector}
mkdir -p context
mkdir -p security/{approval,sandbox,middleware,policy,audit}
mkdir -p execution/{runtime,streaming,persistence,resume,workflow}
mkdir -p observation/{hooks,metrics,eval}
mkdir -p infra/{db,cache,config}
mkdir -p api/{routes,dto}
mkdir -p agent/builtin
mkdir -p skills/builtin
mkdir -p tests/{unit/{model,tools,security,execution,memory,planning,observation},integration}
```

---

### Step 1 — 修复拼写错误 ✅ 已完成，跳过

> `settings_service.py` 拼写已正确，`approval_toutes.py` pycache 文件已不存在，本步无需操作。

---

### Step 2 — 迁移安全层（收益高，风险低）

安全层是最完整的横切关注点，迁出后执行层和其他层的代码都会干净很多。

```bash
# middleware
git mv application/runtime/middleware/base.py     security/middleware/base.py
git mv application/runtime/middleware/approval.py security/approval/middleware.py
git mv application/runtime/middleware/sandbox.py  security/sandbox/middleware.py

# service & store
git mv application/services/approval_service.py  security/approval/service.py
git mv infrastructure/database/repositories/approval_store.py security/approval/store.py
```

更新所有 import 路径，运行测试（`test_approval.py` `test_middleware.py` `test_permission.py`）。

---

### Step 3 — 迁移工具层

```bash
git mv infrastructure/tools/tool_registry.py tools/registry.py
git mv infrastructure/tools/builtin/fs_list.py   tools/builtin/filesystem/fs_list.py
git mv infrastructure/tools/builtin/fs_read.py   tools/builtin/filesystem/fs_read.py
git mv infrastructure/tools/builtin/fs_write.py  tools/builtin/filesystem/fs_write.py
git mv infrastructure/tools/builtin/fs_search.py tools/builtin/filesystem/fs_search.py
git mv infrastructure/tools/builtin/web_search.py tools/builtin/search/web_search.py
git mv infrastructure/tools/builtin/spawn_child_agent.py  tools/builtin/agent_bridge/spawn_child_agent.py
git mv infrastructure/tools/builtin/check_child_status.py tools/builtin/agent_bridge/check_child_status.py
git mv infrastructure/tools/builtin/wait_child_agent.py   tools/builtin/agent_bridge/wait_child_agent.py
git mv infrastructure/tools/builtin/echo.py tools/builtin/util/echo.py

# os_proxy — OS 级工具归入 tools/builtin/util/
git mv infrastructure/os_proxy/apple_script.py tools/builtin/util/apple_script.py
# 若 os_proxy/ 下还有其他文件，按性质归入 filesystem/ 或 util/，然后删除空目录
rmdir infrastructure/os_proxy

# 从 core/tool_types.py 提取接口定义到 tools/protocol.py
```

运行测试（`test_tool_registry.py` `test_tool_pipeline.py`）。

---

### Step 4 — 迁移提示词层

```bash
# 静态模板
git mv infrastructure/agents/builtin/assistant.md         prompt/templates/system/assistant.md
git mv infrastructure/agents/builtin/default.md           prompt/templates/system/default.md
git mv infrastructure/agents/builtin/software_engineer.md prompt/templates/system/software_engineer.md

# 动态构建逻辑
git mv application/runtime/context/prompt_builder.py prompt/builder.py

# 策略
git mv infrastructure/llm/thinking_styles.py prompt/strategies/thinking.py
```

---

### Step 5 — 迁移模型层

```bash
git mv infrastructure/llm/chat_completions_adapter.py model/adapters/chat_completions.py
git mv infrastructure/llm/model_adapter_protocol.py   model/adapters/protocol.py
git mv infrastructure/llm/model_types.py              model/types/model_types.py
```

运行测试（`test_model_adapter.py`）。

---

### Step 6 — 迁移记忆层与上下文层

记忆层和上下文层边界厘清是这步的核心工作：
compaction 的**算法**归 `context/compaction.py`，**触发时机和存储**归 `memory/summary/service.py`。

```bash
# 记忆层
git mv application/services/session_service.py   memory/session/service.py
git mv application/services/workspace_service.py memory/workspace/service.py
git mv application/services/compact_service.py   memory/summary/service.py
git mv infrastructure/database/repositories/session_store.py   memory/session/store.py
git mv infrastructure/database/repositories/workspace_store.py memory/workspace/store.py

# 上下文层
git mv application/runtime/context/compaction.py context/compaction.py
git mv application/services/skill_context_service.py context/skill_context.py
```

运行测试（`test_session_store.py` `test_workspace.py`）。

---

### Step 7 — 迁移执行层并重命名

```bash
git mv application/runtime/agent_runtime.py    execution/runtime/agent_runtime.py
git mv application/runtime/executor.py         execution/runtime/agent_executor.py
git mv application/runtime/tool_executor.py    execution/runtime/tool_runner.py
git mv application/runtime/response_handler.py execution/runtime/response_handler.py
git mv application/runtime/message_builder.py  execution/runtime/message_builder.py
git mv application/runtime/sse_utils.py        execution/streaming/sse.py
git mv application/runtime/tool_run_observer.py observation/hooks/tool_run_observer.py

git mv application/services/run/run_service.py         execution/persistence/run_service.py
git mv application/services/run/run_persistence.py     execution/persistence/run_persistence.py
git mv application/services/run/run_context_builder.py execution/persistence/run_context_builder.py
git mv application/services/run/stream_run_session.py  execution/streaming/stream_run_session.py
git mv application/services/run/resume_run_service.py  execution/resume/resume_run_service.py
```

运行测试（`test_agent_runtime.py` `test_spawn_child_agent.py` `test_parallel_child_agents.py`）。

---

### Step 8 — 搬迁测试文件

```bash
# 单元测试
git mv tests/test_model_adapter.py           tests/unit/model/test_model_adapter.py
git mv tests/test_tool_registry.py           tests/unit/tools/test_tool_registry.py
git mv tests/test_approval.py                tests/unit/security/test_approval.py
git mv tests/test_middleware.py              tests/unit/security/test_middleware.py
git mv tests/test_permission.py             tests/unit/security/test_permission.py
git mv tests/test_agent_runtime.py           tests/unit/execution/test_agent_runtime.py
git mv tests/test_spawn_child_agent.py       tests/unit/execution/test_spawn_child_agent.py
git mv tests/test_parallel_child_agents.py  tests/unit/execution/test_parallel_child_agents.py
git mv tests/test_session_store.py           tests/unit/memory/test_session_store.py
git mv tests/test_workspace.py              tests/unit/memory/test_workspace.py

# 集成测试
git mv tests/test_agent_api.py                   tests/integration/test_agent_api.py
git mv tests/test_agent_definition_service.py    tests/integration/test_agent_definition_service.py
git mv tests/test_skill_loader.py                tests/integration/test_skill_loader.py
```

更新 `pyproject.toml` 或 `pytest.ini` 的 `testpaths`，确认 `pytest` 可发现所有测试。

---

### Step 9 — 整理剩余目录，补建观测层

```bash
# infra
git mv infrastructure/database/db.py     infra/db/engine.py
git mv infrastructure/database/models.py infra/db/orm_models.py

# agent
git mv core/agent_definition.py  agent/definition.py
git mv infrastructure/agents/agent_loader.py agent/loader.py
git mv application/services/settings_service.py agent/settings_service.py

# skills
git mv application/services/skill_service.py      skills/service.py
git mv infrastructure/skills/skill_loader.py      skills/loader.py
git mv infrastructure/skills/skill_config.py      skills/config.py

# api
git mv interface/api/routes/ api/routes/
git mv interface/api/app.py  api/app.py
git mv interface/dto/        api/dto/
# common.py → dependencies.py
git mv api/routes/common.py api/routes/dependencies.py

# 观测层：补建骨架并接入 trace_routes
touch observation/tracer.py observation/logger.py

# 修复 alembic — ORM 路径已变，需同步更新 env.py
# 将 target_metadata 的 import 从旧路径改为新路径：
# from infrastructure.database.models import Base
# → from agent_prototype.infra.db.orm_models import Base
# 同时确认 alembic.ini 中 script_location 指向正确
```

运行全量测试，确认集成测试通过（`test_agent_api.py` `test_agent_definition_service.py`）。

---

## 六、迁移完成检查清单

```
[ ] application/ 目录已完全消失
[ ] infrastructure/ 目录已完全消失（或只剩空壳）
[ ] core/ 目录已完全消失
[ ] interface/ 目录已完全消失
[ ] infrastructure/os_proxy/ 已完全消失
[ ] 所有 import 路径已更新
[ ] 没有 _utils、common、setting_services 等问题命名
[ ] infra/db/ 下没有 db.py，只有 engine.py 和 orm_models.py
[ ] alembic/env.py 的 target_metadata import 已指向 infra.db.orm_models
[ ] `alembic upgrade head` 可正常执行
[ ] 全量测试通过（14 个测试文件，均在 tests/unit/ 或 tests/integration/ 下）
[ ] 每个新目录有 README 说明职责契约
[ ] 新目录树与本文档目录树一致
```
