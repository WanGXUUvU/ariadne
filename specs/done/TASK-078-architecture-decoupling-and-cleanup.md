# TASK-078 - 整体架构极致重构解耦与九层模型边界彻底清洗

## 1. 目标 (Goal)
在推进具体业务特性之前，优先对迁移后的后端物理代码进行彻底的“化学解耦”与职责边界清洗，贯彻“每个部分只涉及每个部分”的极致解耦原则：
1. **L1 模型层绝对底层化**：修正 `model/adapters/chat_completions.py` 中的 `ChatMessage` 越权依赖，消除与 DTO 的循环引用。
2. **L2 提示词层彻底无状态化**：剥离 `prompt/builder.py` 内部的文件系统物理磁盘读取，使其专注于纯粹、无损的指令拼接。
3. **L3 工具层完全代理化（核心突破 🔥）**：
   - 彻底斩断 `spawn_child_agent.py` 对 L8 执行器（`AgentRunner`）和 L5 数据库层（`SessionLocal` / `SessionStore`）的循环越权依赖；
   - 彻底移出 `check_child_status.py` 和 `wait_child_agent.py` 对 Python `concurrent.futures.Future` 类型的直接操作；
   - 通过 L8 引擎侧在组装 ToolRegistry 时，动态注入三个“三纯”回调（派发器、状态查询器、阻塞等待器）完成工具层与执行/持久化层的终极解耦。
4. **L5 记忆层去智能化**：剥离 `memory/summary/service.py` 内部的大模型调用交互（移入 L6），使 L5 专注于纯粹的持久化快照存取与 runs 活跃标志位维护。
5. **L6 上下文装配总调度落地**：在 `context/` 落地 `assembler.py` 统一上下文装配器（`ContextAssembler`），统筹调度历史提取、大模型有损压缩、Skill加载及指令合成。

---

## 2. 新任务拆解模板 (Task Teardown Template)

```text
用户动作：
1. 本地运行 pytest 进行自动化验证。
2. 在前端或 CLI 中创建会话，执行流式问答，或者拉起子智能体任务。

用户会看到：
1. 所有 96 个单元/集成测试继续 100% 保持通过，功能完全无损（向后兼容）。
2. 代码结构具备极高的内聚度，各层之间的 import 完全符合九层模型边界，无任何越权依赖。

新数据从哪里产生：
无新业务数据产生（纯粹的架构精细化解耦与重构）。

新数据要存在哪里：
无（数据库 schema 和持久化策略保持完全一致）。

前端调哪个接口：
无变更（API 接口层完全向后兼容）。

need改的层：
1. 模型层 (model/adapters/chat_completions.py): 调整 ChatMessage 的 import，回归纯领域模型。
2. 提示词层 (prompt/builder.py): 移出 I/O 操作，参数升级为纯 string。
3. 记忆层 (memory/summary/service.py): 移出 LLM 接口调用与 Adapter 构建。
4. 上下文层 (context/compaction.py & context/assembler.py): 落地 ContextAssembler，承接大模型压缩和工作区磁盘读取。
5. 工具层 (tools/builtin/agent_bridge/spawn_child_agent.py, check_child_status.py, wait_child_agent.py): 移出对 L8/L5 的依赖，改用回调注入。
6. 执行层 (execution/persistence/run_context_builder.py & run_service.py): 适配 ContextAssembler 组装及工具注册回调注入。
```

---

## 3. 切片迭代路线 (Checklist)

- [ ] **切片 1：L1 模型层依赖纠偏与 L2 提示词层无状态解耦**
  - [ ] 修改 `backend/model/adapters/chat_completions.py`，直接从 `backend.model.types.domain` 导入 `ChatMessage`，消除对 API DTO 的越权依赖。
  - [ ] 重构 `backend/prompt/builder.py` 的 `build_runtime_system_prompt`：
    - 移除对工作区文件（`AGENTS.md` / `SOUL.md` / `USER.md`）的物理路径磁盘读取（`workspace_path` 参数删除）；
    - 修改其参数，直接接受已读取好的文本内容 `local_rules_text: Optional[str]`、`agent_soul_text: Optional[str]`、`user_profile_text: Optional[str]`。
  - [ ] **⚠️ 同步修改 `backend/context/skill_context.py`**（此文件调用了 `build_runtime_system_prompt(..., workspace_path=workspace_path)`，切片 1 完成后此处直接编译报错，必须一并处理）：
    - 将 `workspace_path` 从 `build_runtime_definition_with_skills` 的传参中移除；
    - `session_type` 和文件内容文本（`local_rules_text` 等）改由切片 2 中的 `ContextAssembler` 负责读取后传入。
  - [ ] 运行模型层和提示词层相关测试，确保基础逻辑通过。

- [ ] **切片 2：L6 统一上下文装配器（ContextAssembler）落地与 L5 记忆压缩去推理化**
  - [ ] 在 `backend/context/assembler.py` 中落地 `ContextAssembler` [NEW]：
    - 负责接收 `session_type`、`workspace_path`，处理物理磁盘 `AGENTS.md` / `SOUL.md` / `USER.md` 的读取；
    - 调用 `SkillContextService` 获取技能目录文本，再调用 L2 `build_runtime_system_prompt` 拼装最终 system prompt；
    - 返回 `AssembledContext`（dataclass：`system_prompt: str`，`workspace_path: str | None`）供 `RunContextBuilder` 使用。
  - [ ] 在 `backend/context/compaction.py` 中新增 `HistoryCompactor` 类（⚠️ 接口约定如下，落地时不得偏离）：
    ```python
    class HistoryCompactor:
        def __init__(self, adapter: ModelAdapter): ...
        def compact(self, messages: list[ChatMessage], keep_recent: int) -> str:
            """调用 LLM 生成中段摘要文本，返回摘要字符串。"""
    ```
  - [ ] 重构 `backend/memory/summary/service.py` 内部的 `CompactService`（⚠️ 此处有两条并行违规，须同步修复）：
    - **违规 A（L5→L1 跳 L6）**：移除其内部对 `ChatCompletionsAdapter` 实例化、`ModelRequest` 构建和 `adapter.generate(request)` 的直接大模型调用；`auto_compact_in_memory` 改为接收外部传入的 `compactor: Optional[HistoryCompactor]`（原 `adapter` 参数替换）。
    - **违规 B（L5→L8）**：第 34 行 `from backend.execution.persistence.run_context_builder import RunContextBuilder` — L5 记忆层直接引用 L8 执行层的 `RunContextBuilder` 来构建 LLM 请求上下文，与违规 A 同根（LLM 请求构建逻辑不应在 L5 内部），随违规 A 一并剥出；`CompactService` 完成修复后不再持有任何 L8 依赖。
    - 修复后 `CompactService` 只负责 Snapshot 的持久化状态存取与 Run 活跃标志位修改。
  - [ ] 运行测试确认历史管理与压缩链路完全无损。

- [ ] **切片 3：L3 子智能体派发工具与 L8 执行层“三纯回调”依赖倒置解耦**
  - [ ] 重构 `backend/tools/builtin/agent_bridge/spawn_child_agent.py`：
    - 彻底删除对 `agent_runtime.py`、`SqliteSessionStore`、`RunContextBuilder`、`SessionLocal` 等类和模块的导入；
    - 改造为接收闭包派发器 `child_dispatcher: Callable[[str, str], str]`（参数：`task, agent_name`，返回 `child_run_id`）；
    - `_run_child` 整体迁入 `run_service.py` 作为私有实现。
  - [ ] 重构 `backend/tools/builtin/agent_bridge/check_child_status.py`：
    - 彻底移出对 Python `concurrent.futures.Future` 对象的直接操作与 `futures` 字典导入；
    - 改造为接收状态查询器回调 `status_checker: Callable[[list[str]], dict[str, Any]]`。
  - [ ] 重构 `backend/tools/builtin/agent_bridge/wait_child_agent.py`：
    - 彻底移出对 `f.result` 的直接操作与超时等待逻辑（超时逻辑一并移至 L8）；
    - 改造为接收阻塞等待器回调 `child_waiter: Callable[[str], str]`。
  - [ ] 重构 `backend/tools/registry.py` 中的 `build_run_registry` 签名，移除 `executor`/`futures` 参数：
    ```python
    def build_run_registry(
        child_dispatcher: Callable[[str, str], str],
        status_checker:   Callable[[list[str]], dict],
        child_waiter:     Callable[[str], str],
    ) -> ToolRegistry
    ```
  - [ ] 在 `backend/execution/persistence/run_service.py` 内部实现并注入三个回调闭包：
    - **⚠️ `_executor` 和 `_global_futures` 保持定义在 `execution/runtime/agent_executor.py`，不挪动**；`run_service.py` 继续 import 它们，三个闭包 close over 即可。
    - `_make_child_dispatcher(parent_run_id, session_id, db) -> Callable`：负责 submit 线程、写 futures 字典、落库子 run 记录（含原 `_run_child` 逻辑）。
    - `_make_status_checker() -> Callable`：读 `_global_futures` 各 Future 状态，返回 `{run_id: {status, reply?, error?}}`。
    - `_make_child_waiter() -> Callable`：对指定 future 调 `.result(timeout=120)`，超时返回错误结构。
  - [ ] **⚠️ 同步重写 `tests/unit/execution/test_spawn_child_agent.py` 和 `tests/unit/execution/test_parallel_child_agents.py`**（两个文件共 10 处 `build_run_registry(executor=..., futures=...)` 调用，签名变更后全部失效），改为传入 mock 回调。
  - [ ] 运行 `test_spawn_child_agent.py` 和 `test_parallel_child_agents.py` 确认子智能体异步派发机制全绿通过。

- [ ] **切片 4：全量测试与向后兼容保障**
  - [ ] 调整 `backend/execution/persistence/run_context_builder.py`：
    - 引入 `ContextAssembler`，将 `SkillContextService.build_runtime_definition_with_skills` 的调用替换为 `ContextAssembler.assemble()`；
    - `RunContextBuilder` 不再持有文件读取逻辑，全部委托给 `ContextAssembler`。
  - [ ] 运行项目全量测试，确保 100% 绿灯。
  - [ ] 确保在重构解耦后可以实现完美的业务功能向后兼容。

---

## 4. 改前 / 改后完整依赖矩阵

> ✅ 合法向下依赖  ⚠️ 待修复越权  🔴 严重越权

| 层 | 文件 | 当前违规依赖 | 改后目标 |
|---|---|---|---|
| L1 | `model/adapters/chat_completions.py` | ⚠️ `api.dto.schemas.ChatMessage`（L1 引 API 层）| ✅ `model.types.domain.ChatMessage` |
| L2 | `prompt/builder.py` | ⚠️ `os.path` 磁盘 I/O（L2 含副作用）| ✅ 接收 `local_rules_text` 等纯字符串参数 |
| L3 | `tools/builtin/agent_bridge/spawn_child_agent.py` | 🔴 `AgentRunner`（L8）+ `RunContextBuilder`（L8）+ `SessionLocal`（infra）+ `SqliteSessionStore`（L5）| ✅ 仅接收 `child_dispatcher: Callable` |
| L3 | `tools/builtin/agent_bridge/check_child_status.py` | ⚠️ `concurrent.futures.Future` 直接操作（L8 机制泄漏 L3）| ✅ 仅接收 `status_checker: Callable` |
| L3 | `tools/builtin/agent_bridge/wait_child_agent.py` | ⚠️ `f.result(timeout=120)` 直接调用（同上）| ✅ 仅接收 `child_waiter: Callable` |
| L5 | `memory/summary/service.py` | ⚠️ new `ChatCompletionsAdapter` + `.generate()`（L5 越过 L6 直调 L1）<br>🔴 line 34: `RunContextBuilder`（L5 直引 L8 执行层）| ✅ 接收外部注入的 `HistoryCompactor` 实例，移除 L8 依赖 |
| L6 | `context/skill_context.py` | ⚠️ `build_runtime_system_prompt(workspace_path=...)` 触发间接磁盘 I/O | ✅ 移除 `workspace_path`，接收已读好的文本 |
| L6 | `context/assembler.py` | ❌ 不存在 | ✅ 新建：磁盘读取 + Skill 拼装 + 调 L2 |
| L6 | `context/compaction.py` | 仅纯函数，无 LLM 调用 | ✅ 新增 `HistoryCompactor` 类，封装 adapter 调用 |
| L8 | `execution/runtime/agent_executor.py` | ✅ 自治，定义 `_executor`、`_global_futures` | **不变**，继续作为线程池与 futures 的物理归属地 |
| L8 | `execution/persistence/run_service.py` | ⚠️ 直接传 `executor`、`futures` 给 `build_run_registry`（L8 实现细节外泄到 L3）| ✅ 构造三个闭包 close over executor/futures 后注入 `build_run_registry` |

**改后仍保留的跨层引用（超出本次 scope，由 TASK-079 / TASK-080 专项解决）：**
- **[TASK-079]** `api/dto/schemas.py` 充当全局类型中心（22 处），`AgentState`、`AgentEvent`、`AgentInput`、`SkillSummary`、`StreamFrame` 等领域类型错误归位于 API 层 → 迁移至 `model/types/agent.py`、`skills/types.py`、`execution/streaming/types.py`。
- **[TASK-079]** `AgentDefinition` 定义在 `agent/definition.py`（L10），被 execution（L8）、context（L6）广泛引用，造成 8 处"低层引用高层"假违规 → 将 `AgentDefinition` 归位至 `model/types/` 或独立配置层（低于 L8）。
- **[TASK-080]** `execution/run_service.py`、`execution/streaming/stream_run_session.py` → `observation/hooks/tool_run_observer`（L8→L9）→ 改为事件注册/Hook 注入模式，L9 主动订阅 L8 事件，而非 L8 主动 import L9。
- **[TASK-080]** `memory/session/service.py` → `security/policy.PROFILES`（L5→L7）→ 将 `PROFILES` 默认值下移至 `model/types/` 或通过参数注入，消除 L5 对 L7 的上行依赖。
