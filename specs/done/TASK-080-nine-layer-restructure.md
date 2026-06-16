# TASK-080 - 九层模型重构

> 目标：将项目目录结构对齐九层能力模型，消除 `core/` 中心文件，类型归位到各自的语义层。
> 原则：保留已有的优秀改动（如各层 types.py 独立、StreamFrame 归位等），只修实际违规项。

---

## 九层模型定义

| 层级 | 目录 | 职责 | 依赖方向 |
|------|------|------|----------|
| L1 | `model/` | 模型适配器 + LLM 协议原语 | 只依赖 infra/ |
| L2 | `prompt/` | 提示词拼接 + 策略 | 依赖 model/（类型） |
| L3 | `tools/` | 工具注册与实现 | 依赖 infra/ |
| L4 | `planning/` | 规划器 | 依赖 prompt/ tools/ |
| L5 | `memory/` | 持久化存取 | 依赖 infra/db/ |
| L6 | `context/` | 上下文组装 | 依赖 memory/ prompt/ |
| L7 | `security/` | 权限与安全 | 依赖 infra/ |
| L8 | `execution/` | 执行与编排 | 编排者，可依赖任意层 |
| L9 | `observation/` | 观测与评估 | 只读 hook |

**跨层能力包**（不属于九层，独立顶层）：`agent/`、`skills/`、`api/`、`infra/`

---

## 现状差异分析

### 已到位（保留不动）
- ✅ `prompt/` — builder + strategies + templates，结构正确
- ✅ `tools/` — registry + builtin 分类，结构正确
- ✅ `execution/` — runtime/streaming/persistence/resume，结构正确
- ✅ `context/` — assembler + compaction + skill_context，结构正确
- ✅ `security/` — approval/sandbox/middleware/policy，结构正确
- ✅ `memory/` — session/workspace/summary/run，结构正确
- ✅ `observation/` — tracer + logger + tool_run_observer，结构正确
- ✅ `infra/` — db + os_proxy，结构正确
- ✅ `api/` — routes + dto，结构正确
- ✅ `skills/` — service + loader + types，结构正确
- ✅ 各层 `types.py` 已独立（tools/types, execution/*/types, context/types, security/types, skills/types）
- ✅ `StreamFrame` 已归位到 `execution/streaming/types.py`
- ✅ `SkillSummary` 已归位到 `skills/types.py`
- ✅ `ToolCallContext` 已归位到 `security/middleware/base.py`

### 需要修改的

#### 1. 消灭 `core/` 目录 — 类型按语义归位

`core/types.py` 是 416 行的巨型文件，所有类型堆在一起。需要按语义拆散：

| 类型 | 当前位置 | 应归位到 | 理由 |
|------|----------|----------|------|
| `ToolCallFunction`, `ToolCall`, `ToolError`, `ToolResult` | core/types | **model/types/domain.py** | LLM 协议原语，与模型层同层 |
| `ChatMessage` | core/types | **model/types/domain.py** | LLM 对话原语 |
| `RiskLevel` | core/types | **tools/types.py** | 工具层概念，已被 tools/types.py import |
| `AgentDefinition`, `DEFAULT_AGENT_DEFINITION`, `ASSISTANT_AGENT_DEFINITION` | core/types | **agent/types.py** | Agent 定义层的类型 |
| `AgentState`, `AgentEvent` | core/types | **execution/persistence/types.py** | 运行时状态/事件 |
| `AgentInput`, `AgentOutput`, `FinalizeRunInput`, `RunMetadata` | core/types | **execution/persistence/types.py** | Run I/O |
| `CompactInput`, `CompactOutput` | core/types | **memory/summary/types.py** | 压缩领域类型 |
| `CreateSessionInput`, `RenameSessionInput`, `ResetInput`, `SessionSummary` | core/types | **memory/session/types.py** | Session 领域类型 |
| `ProviderOut`, `ModelOut` | core/types | **agent/settings/types.py** | 设置领域类型 |
| `ModelConfig`, `ModelRequest`, `ModelUsage`, `ModelError`, `ModelResponse`, `ModelStreamEvent` | core/types | **model/types/domain.py** | 模型通信协议 |
| `ModelAdapter` (Protocol) | core/types | **model/adapters/protocol.py** | 模型适配器协议 |

#### 2. `core/adapters/` → `model/`

| 文件 | 当前位置 | 应归位到 |
|------|----------|----------|
| `chat_completions.py` | core/adapters/ | **model/adapters/chat_completions.py** |
| `protocol.py` | core/adapters/ | **model/adapters/protocol.py** (与 ModelAdapter Protocol 合并) |

#### 3. 消灭 `agent/types.py` 的 re-export

当前 `agent/types.py` 只是从 `core.types` re-export `AgentDefinition` 等类型。
类型归位到 `agent/types.py` 后，这个 re-export 自然消失，`agent/types.py` 变成类型的真正定义处。

#### 4. 小项清理

| 问题 | 修复 |
|------|------|
| `tools/builtin/system/apple_script.py` 与 `infra/os_proxy/apple_script.py` 重复 | 删除 `tools/builtin/system/`，保留 `infra/os_proxy/` |
| `agent/settings/` 目录下 service.py + store.py 在 agent/ 下合理 | 保留不动 |

---

## 执行步骤

### Step 1: 创建 `model/` 目录，搬迁 core/adapters/

```
core/adapters/chat_completions.py → model/adapters/chat_completions.py
core/adapters/protocol.py         → model/adapters/protocol.py (暂保留)
```

- 更新所有 `from backend.core.adapters` 的 import
- 涉及文件：execution/persistence/builder.py, execution/persistence/types.py, memory/summary/service.py, tests/

### Step 2: 创建 `model/types/domain.py`，搬迁 LLM 协议原语

从 `core/types.py` 迁出：
- `ToolCallFunction`, `ToolCall`, `ToolError`, `ToolResult`
- `ChatMessage`
- `ModelConfig`, `ModelRequest`, `ModelUsage`, `ModelError`, `ModelResponse`, `ModelStreamEvent`

`model/types/__init__.py` 做 re-export。

### Step 3: 将 `ModelAdapter` Protocol 合并到 `model/adapters/protocol.py`

当前 `core/adapters/protocol.py` 只有一个空壳，`ModelAdapter` 定义在 `core/types.py`。
合并后 `model/adapters/protocol.py` 包含 Protocol 定义。

### Step 4: 各领域类型归位

- `RiskLevel` → `tools/types.py`（已有文件，追加）
- `AgentDefinition` 等 → `agent/types.py`（改为真正定义，不再 re-export）
- `AgentState`, `AgentEvent` → `execution/persistence/types.py`（已有文件，追加）
- `AgentInput`, `AgentOutput`, `FinalizeRunInput`, `RunMetadata` → `execution/persistence/types.py`
- `CompactInput`, `CompactOutput` → 新建 `memory/summary/types.py`
- `CreateSessionInput`, `RenameSessionInput`, `ResetInput`, `SessionSummary` → 新建 `memory/session/types.py`
- `ProviderOut`, `ModelOut` → 新建 `agent/settings/types.py`

### Step 5: 全局 import 路径修正

更新所有 61 处 `from backend.core.types import` 和 5 处 `from backend.core.adapters import`。

### Step 6: 删除 `core/` 目录

确认无任何 import 指向 core/ 后，删除整个 core/ 目录。

### Step 7: 删除 `tools/builtin/system/` 重复目录

`apple_script.py` 在 `infra/os_proxy/` 已有，删除 `tools/builtin/system/`。

### Step 8: 验证

```bash
python -c "import backend; print('OK')"
python -m pytest backend/tests/ -x -q
```

---

## 层间依赖规则（迁移后生效）

```
observation/  →  只读 hook，可依赖任意层，禁止修改任何层的行为
execution/    →  编排者，通过协议调用各层，是唯一允许横向依赖的层
security/     →  横切关注点，依赖 infra/，禁止依赖 context/ planning/
planning/     →  依赖 prompt/ tools/（协议），禁止直接调用 execution/
context/      →  依赖 memory/ prompt/，禁止依赖 execution/ planning/
memory/       →  依赖 infra/db/，禁止依赖 context/ execution/
tools/        →  依赖 infra/，禁止依赖 planning/ execution/
prompt/       →  依赖 model/（类型），禁止依赖 execution/ memory/
model/        →  依赖 infra/，禁止依赖所有业务层
infra/        →  无业务依赖，只做技术适配
```

---

## 检查清单

- [ ] `core/` 目录已完全消失
- [ ] `model/` 目录包含 adapters/ + types/
- [ ] `agent/types.py` 是真正定义（非 re-export）
- [ ] 各层 types.py 只含本层领域类型
- [ ] 无任何 `from backend.core` import
- [ ] `python -c "import backend"` 通过
- [ ] `python -m pytest backend/tests/ -x -q` 通过
