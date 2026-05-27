# TASK-079 - 领域类型归位：消除 api/dto/schemas 充当全局类型中心的 22 处违规

## 1. 目标 (Goal)

`api/dto/schemas.py` 目前同时承担两个职责：
1. HTTP 请求/响应体（正确，应该留在这里）
2. 领域核心类型（错误，被 10 个不同层引用，造成所有层向上依赖 API 层）

本任务将领域类型从 `api/dto/schemas.py` 中剥离，归位至各自所属的低层模块，使 `api/dto/schemas.py` 成为一个**纯 HTTP I/O 形状文件**。

完成后，`api.dto.schemas` 只被 `api/routes/` 及测试引用，所有业务层只从 `model/`、`skills/`、`execution/` 等低层引用类型。

---

## 2. 违规现状（共 22 处非 API 层引用）

通过静态扫描确认，以下非 API 层文件引用了 `api.dto.schemas`：

| 文件（源层） | 引用的类型 |
|---|---|
| `model/adapters/chat_completions.py` (L1) | `ChatMessage` |
| `prompt/builder.py` (L2) | `SkillSummary` |
| `tools/builtin/agent_bridge/spawn_child_agent.py` (L3) | `AgentInput`, `AgentState` |
| `security/approval/store.py` (L7) | `ChatMessage` |
| `memory/session/store.py` (L5) | `AgentEvent`, `AgentState`, `ChatMessage` |
| `memory/session/service.py` (L5) | `AgentState` 等 |
| `memory/summary/service.py` (L5) | `AgentState`, `CompactInput`, `CompactOutput`, `ChatMessage` |
| `context/compaction.py` (L6) | `AgentState`, `CompactOutput` |
| `context/skill_context.py` (L6) | `AgentInput`, `SkillSummary` |
| `execution/persistence/run_context_builder.py` (L8) | `AgentInput`, `AgentState`, `ApprovalPolicy` |
| `execution/persistence/run_persistence.py` (L8) | `AgentInput`, `AgentOutput`, `AgentState`, `ChatMessage`, `RunMetadata` |
| `execution/persistence/run_service.py` (L8) | 多个 |
| `execution/resume/resume_run_service.py` (L8) | 多个 |
| `execution/runtime/agent_runtime.py` (L8) | 多个 |
| `execution/runtime/message_builder.py` (L8) | `AgentState`, `ChatMessage` |
| `execution/runtime/response_handler.py` (L8) | `AgentEvent`, `ChatMessage` |
| `execution/runtime/tool_runner.py` (L8) | 多个 |
| `execution/streaming/sse.py` (L8) | `StreamFrame` |
| `execution/streaming/stream_run_session.py` (L8) | 多个 |
| `observation/hooks/tool_run_observer.py` (L9) | `AgentEvent`, `AgentInput`, `AgentState` |
| `agent/settings_service.py` | `ModelOut`, `ProviderOut` |
| `skills/loader.py` / `skills/service.py` | `SkillSummary` |

---

## 3. 类型归位方案

### 3.1 新建 `model/types/agent.py` — 运行时核心领域类型

将以下类型从 `api/dto/schemas.py` **剪切**到此文件：

```
AgentState        — session 状态快照，被 L5/L6/L8/L9 大量使用
AgentEvent        — run 中的结构化事件，被 L8/L9 使用
AgentInput        — /run 请求语义对象（非 HTTP 形状），被 L3/L8 使用
AgentOutput       — /run 响应语义对象，被 L8 使用
RunMetadata       — run 轻量元信息，被 L8/tests 使用
FinalizeRunInput  — run 完成时内部写库用，仅 L8 使用
StreamFrame       — SSE 推送帧结构（可移至 execution/streaming/types.py，见 3.3）
```

`api/dto/schemas.py` 改为从此处 re-export（**零破坏过渡**），迁移全量测试通过后再删 re-export。

### 3.2 新建 `skills/types.py` — Skill 领域类型

将以下类型从 `api/dto/schemas.py` **剪切**到此文件：

```
SkillSummary  — skill 元数据，被 L2 prompt/builder.py、L6 context/skill_context.py、skills/ 自身使用
```

### 3.3 新建 `execution/streaming/types.py` — 流式推送类型

将以下类型从 `api/dto/schemas.py` **剪切**到此文件：

```
StreamFrame  — 仅被 execution/streaming/sse.py 和 stream_run_session.py 使用
```

### 3.4 `api/dto/schemas.py` 改后只保留 HTTP I/O 形状

改后此文件仅保留（含从低层 import 后组合的类型）：

```
ToolCallSummary       RunDetailResponse     CreateSessionInput
RenameSessionInput    ResetInput            SessionSummary
SessionDetail         TraceRunSummary       TraceResponse
CompactInput          CompactOutput         WorkspaceSummary
CreateProviderInput   ProviderOut           PatchProviderInput
PatchModelInput       ModelOut              ApiError
ErrorResponse
```

---

## 4. 新任务拆解模板

```text
用户动作：运行 pytest 验证。

用户会看到：全量测试 100% 通过，所有层的 import 路径指向低层模块，
            api.dto.schemas 不再被任何非 API 层文件直接引用。

新数据从哪里产生：无（纯重构，无业务逻辑变更）。

新数据要存在哪里：无（DB schema 不变）。

前端调哪个接口：无变更（API 接口完全向后兼容）。

need改的层：
  - model/types/agent.py    [新建，剪入 7 个领域类型]
  - skills/types.py          [新建，剪入 SkillSummary]
  - execution/streaming/types.py  [新建，剪入 StreamFrame]
  - api/dto/schemas.py       [改为 re-export + 精简]
  - 22 处引用文件            [将 from api.dto.schemas import X 改为 from model.types.agent import X 等]
```

---

## 5. 切片迭代路线 (Checklist)

- [ ] **切片 1：建立归位目标文件**
  - [ ] 新建 `agent_prototype/model/types/agent.py`，将 `AgentState`、`AgentEvent`、`AgentInput`、`AgentOutput`、`RunMetadata`、`FinalizeRunInput` 定义搬入。
  - [ ] 新建 `agent_prototype/skills/types.py`，将 `SkillSummary` 定义搬入。
  - [ ] 新建 `agent_prototype/execution/streaming/types.py`，将 `StreamFrame` 定义搬入。
  - [ ] `api/dto/schemas.py` 在原位置加 re-export（`from agent_prototype.model.types.agent import AgentState, ...`），确保现有 import 零破坏。
  - [ ] 运行全量测试，确认全绿（此时改动为零破坏）。

- [ ] **切片 2：迁移 22 处引用**
  - [ ] 将所有非 API 层文件中的 `from agent_prototype.api.dto.schemas import X` 批量改为从对应低层模块引入。
  - [ ] 优先级顺序（从低层到高层，避免中途出现循环）：
    1. `model/adapters/chat_completions.py` → `model.types.domain`（`ChatMessage` 已在 domain，此处是 TASK-078 遗留）
    2. `skills/loader.py`、`skills/service.py` → `skills.types`
    3. `security/approval/store.py` → `model.types.domain`
    4. `memory/` 下各文件 → `model.types.agent`
    5. `context/` 下各文件 → `model.types.agent`、`skills.types`
    6. `execution/` 下各文件 → `model.types.agent`
    7. `observation/` 下各文件 → `model.types.agent`
    8. `agent/settings_service.py` → `api.dto.schemas`（`ModelOut`/`ProviderOut` 是 HTTP 响应体，**保留在 api**，此处无需改动）
  - [ ] 每批改完后运行测试，确保持续绿灯。

- [ ] **切片 3：删除 re-export，清洁 api/dto/schemas.py**
  - [ ] 确认 `api/dto/schemas.py` 的 re-export 行不再被非 API 层引用后，删除所有 re-export 行。
  - [ ] 最终 `api/dto/schemas.py` 只剩 HTTP I/O 形状定义。
  - [ ] 运行全量测试，100% 通过。
  - [ ] （可选）运行静态扫描脚本验证：非 API 层文件中 `from agent_prototype.api` 的 import 数量为 0。

---

## 6. 改前 / 改后依赖矩阵

| 文件 | 改前引用 | 改后引用 |
|---|---|---|
| `model/adapters/chat_completions.py` | `api.dto.schemas.ChatMessage` | `model.types.domain.ChatMessage` |
| `prompt/builder.py` | `api.dto.schemas.SkillSummary` | `skills.types.SkillSummary` |
| `skills/loader.py`, `skills/service.py` | `api.dto.schemas.SkillSummary` | `skills.types.SkillSummary` |
| `security/approval/store.py` | `api.dto.schemas.ChatMessage` | `model.types.domain.ChatMessage` |
| `memory/session/store.py` | `api.dto.schemas.AgentState` 等 | `model.types.agent.AgentState` 等 |
| `memory/summary/service.py` | `api.dto.schemas.AgentState` 等 | `model.types.agent.AgentState` 等 |
| `context/compaction.py` | `api.dto.schemas.AgentState`, `CompactOutput` | `model.types.agent.AgentState` + (CompactOutput 暂留 api 或移 context/types) |
| `context/skill_context.py` | `api.dto.schemas.AgentInput`, `SkillSummary` | `model.types.agent.AgentInput`, `skills.types.SkillSummary` |
| `execution/` 下所有文件 | `api.dto.schemas.*` | `model.types.agent.*` |
| `execution/streaming/sse.py` | `api.dto.schemas.StreamFrame` | `execution.streaming.types.StreamFrame` |
| `observation/hooks/tool_run_observer.py` | `api.dto.schemas.*` | `model.types.agent.*` |

**改后 `api/dto/schemas.py` 只被以下引用（合法）：**
- `api/routes/*.py`（HTTP 路由层）
- `tests/`（测试可以引用任意层）
