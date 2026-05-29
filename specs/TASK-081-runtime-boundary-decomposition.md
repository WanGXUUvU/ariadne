# TASK-081 - 运行时边界拆解：后端双中心收口与前端状态总线分解

## 1. 目标 (Goal)

不继续围绕“目录是否叫 `core/`”打转，直接处理当前真实阻碍演进的三个结构问题：

1. **后端执行链双中心化**
   - `execution/service.py` 与 `execution/persistence/builder.py` 同时承担编排、装配、调度、查询、落库前置逻辑。
   - 结果：一次 run 的主链路没有单一稳定边界，任何新能力都会同时撬动两个大文件。

2. **前端状态总线过度膨胀**
   - `frontend/src/composables/useWorkspace.ts` 同时负责 session、streaming、approval、timeline、child agent、workspace、model config。
   - 结果：前端虽有组件分层，但应用状态仍是单文件总线，功能之间高耦合，回归面过大。

3. **共享协议文件持续吸附领域类型**
   - `core/types.py` 同时承载模型协议、工具结果、运行时状态、事件。
   - 结果：`model / tools / execution` 的边界仍然被一个共享文件绑死，目录分层无法真正落到运行时边界。

本任务不做“大一统九层改名工程”，只做最小但决定性的边界收口：
- 后端：把“运行物料装配”和“运行编排调度”切开；
- 前端：把“工作区门面”和“具体用例状态机”切开；
- 类型：把“模型协议”和“运行时状态”切开。

---

## 2. 新任务拆解模板 (Task Teardown Template)

```text
用户动作：
1. 创建会话，发送消息，触发流式输出、审批、子 Agent、停止运行。
2. 刷新页面，重新打开历史会话，查看 trace、timeline、child agent 状态。

用户会看到：
1. 所有现有接口、交互、SSE 语义保持不变。
2. 前端界面行为不变，但相关逻辑被拆到更小、更稳定的状态模块。
3. 后端 run 主链路更清晰：装配、编排、trace 查询、child agent 调度职责分离。

新数据从哪里产生：
无新业务数据；仅重组运行时职责边界与状态流。

新数据要存在哪里：
无新增持久化表；沿用现有 session / run / approval / settings 数据结构。

前端调哪个接口：
不新增接口；继续使用现有：
- POST /run/stream
- POST /sessions
- GET /sessions/{id}
- GET /sessions/{id}/trace
- POST /approvals/{id}/approve|reject|approve_all

need改的层：
1. execution/：拆分运行时编排、上下文装配、trace 查询、child agent 调度。
2. core/model/execution types：切开模型协议类型与运行时状态类型。
3. frontend/src/composables/：拆分 useWorkspace 单总线。
4. frontend/src/api/：统一 transport 边界，禁止 composable 直接 fetch。
```

---

## 3. 重构原则 (Non-Goals / Guardrails)

### 本卡负责
- 切职责，不改产品语义。
- 拆中心文件，不追求一次性目录完美。
- 保持 API 与前端页面行为向后兼容。

### 本卡不负责
- 不引入新业务功能。
- 不重做数据库 schema。
- 不顺手推进 plugin / MCP / planning 路线。
- 不把所有类型一次性全搬完，只搬“已经造成跨层耦合”的那部分。

---

## 4. 目标边界图 (Target Boundaries)

### 4.1 后端目标边界

#### A. `RuntimeContextFactory`
- 负责什么：
  - 读取 session record
  - 加载 agent definition
  - 构建 model adapter
  - 触发历史压缩评估
  - 产出运行所需的纯物料对象
- 不负责什么：
  - 不启动 AgentRunner
  - 不落库
  - 不处理 child agent
  - 不查询 trace

#### B. `RunOrchestrator`
- 负责什么：
  - 接收 `AgentInput + RuntimeContext`
  - 驱动同步运行 / 流式运行
  - 决定何时接 `StreamRunSession`
- 不负责什么：
  - 不自己读数据库配置
  - 不自己构建 adapter
  - 不自己组装 trace response

#### C. `ChildAgentDispatcher`
- 负责什么：
  - submit 子 Agent
  - 查询状态
  - 等待结果
  - 管理 `_global_futures`
- 不负责什么：
  - 不处理主 run 的上下文装配
  - 不负责 API 层 response 组装

#### D. `TraceQueryService`
- 负责什么：
  - 读取 run records / events
  - 反序列化 `ToolResult`
  - 组装 trace 查询结果
- 不负责什么：
  - 不参与 run 执行
  - 不参与 child agent 调度

### 4.2 前端目标边界

#### A. `useWorkspaceShell`
- 负责什么：
  - 聚合多个子 composable
  - 对视图暴露统一门面
- 不负责什么：
  - 不直接写 streaming 状态机
  - 不直接写 approval 恢复逻辑
  - 不直接写 child polling

#### B. `useSessionState`
- session 列表、activeSession、loadSessionDetail、rename/delete/reset

#### C. `useRunStreaming`
- sendMessage、stopStreaming、timeline 冻结、end 帧收口

#### D. `useApprovalFlow`
- approval_required、approve/reject/approve_all、resume 合并

#### E. `useChildAgentTracker`
- 子 Agent 提取、轮询、状态更新

#### F. `useWorkspaceCatalog`
- workspaces、选择目录、新建会话入口

### 4.3 类型目标边界

#### `core/types.py` 只允许保留
- 真正跨层复用且偏协议的模型通信原语：
  - `ChatMessage`
  - `ModelConfig`
  - `ModelRequest`
  - `ModelResponse`
  - `ModelUsage`
  - `ModelStreamEvent`
  - `ModelAdapter`

#### 应从 `core/types.py` 移出
- 明显属于运行时执行域：
  - `AgentState`
  - `AgentEvent`
- 明显属于工具域：
  - `ToolResult`
  - `ToolError`
  - `ToolCall`
  - `ToolCallFunction`

---

## 5. 切片迭代路线 (Checklist)

### 切片 1：后端执行链切边界
- [x] 新建 `execution/runtime_context_factory.py`
  - [x] 从 `RunContextBuilder` 中移出：session record 读取、agent definition 选择、adapter 构建、approval profile 解析、compaction 触发。
  - [x] 输出稳定的 `RuntimeContext` 对象。
- [x] 新建 `execution/trace_query_service.py`
  - [x] 从 `RunService.get_session_trace()` 中移出 trace 查询与事件反序列化逻辑。
- [x] 新建 `execution/child_agent_dispatcher.py`
  - [x] 从 `RunService` 中移出 `_make_child_dispatcher`、`_make_status_checker`、`_make_child_waiter`、`_run_child_worker`。
- [x] 将 `RunService` 收窄为 façade：
  - [x] `run_agent`
  - [x] `async_stream_agent`
  - [x] `finalize_run`
  - [x] 委托 `TraceQueryService`
  - [x] 委托 `ChildAgentDispatcher`

### 切片 2：共享类型切边界
- [x] 新建 `execution/runtime/types.py`
  - [x] 承接 `AgentState`、`AgentEvent`
- [x] 新建 `tools/result_types.py` 或并入 `tools/types.py`
  - [x] 承接 `ToolCallFunction`、`ToolCall`、`ToolError`、`ToolResult`
- [x] 修正所有 import：
  - [x] `execution/*`
  - [x] `memory/*`
  - [x] `observation/*`
  - [x] `tools/*`
- [x] `core/types.py` 仅保留模型协议原语与 `ModelAdapter`

### 切片 3：前端状态总线拆解
- [x] 新建 `frontend/src/composables/workspace/useSessionState.ts`
- [x] 新建 `frontend/src/composables/workspace/useRunStreaming.ts`
- [x] 新建 `frontend/src/composables/workspace/useApprovalFlow.ts`
- [x] 新建 `frontend/src/composables/workspace/useChildAgentTracker.ts`
- [x] 新建 `frontend/src/composables/workspace/useWorkspaceCatalog.ts`
- [x] 将 `useWorkspace.ts` 降为门面聚合器；文件长度目标压到 250 行以内。

### 切片 4：统一 transport 边界
- [x] 将 `useWorkspace.ts` / 子 composable 中直接 `fetch` 的逻辑全部收口到 `frontend/src/api/`
- [x] 补齐 session patch / model config patch 的 API 封装
- [x] 保证 composable 只依赖 `api/*`，不直接依赖 `fetch`

### 切片 5：回归验证
- [x] 后端：
  - [x] `python3 -m unittest agent_prototype.tests.integration.test_agent_api`
  - [x] `python3 -m unittest discover -s agent_prototype/tests/unit -p 'test_*.py'`
  - [x] `python3 -m compileall agent_prototype`
- [x] 前端：
  - [x] `npm run build`
- [ ] 手动验证主链路：
  - [ ] 新建 session
  - [ ] 发送消息
  - [ ] 流式输出
  - [ ] stop / finalize
  - [ ] approval resume
  - [ ] child agent 展示与轮询

---

## 6. 改前 / 改后依赖矩阵

| 模块 | 改前 | 改后 |
|---|---|---|
| `execution/service.py` | 编排 + child dispatch + trace query + partial finalize | façade only，分别委托 orchestrator / dispatcher / trace query |
| `execution/persistence/builder.py` | session 读取 + adapter 构建 + compaction + prompt 装配 | 仅保留兼容壳，逻辑迁至 `runtime_context_factory.py` |
| `core/types.py` | 模型协议 + 工具结果 + 运行时状态混居 | 仅保留模型协议；工具结果与运行时状态各归其位 |
| `frontend/src/composables/useWorkspace.ts` | 单文件总线 | 门面聚合器 |
| `frontend/src/api/client.ts` + composables | API 层与直接 fetch 混用 | transport 全收口到 `api/*` |

---

## 7. 验收标准 (Definition of Done)

- [x] `RunService` 文件不再持有 child worker / trace 反序列化 / 大段上下文装配逻辑。
- [x] `RunContextBuilder` 或其替代物不再同时承担“数据库配置读取 + adapter 构建 + prompt 装配 + compaction 触发 + agent 选择”全部职责。
- [x] `useWorkspace.ts` 不再是唯一状态总线，拆出至少 4 个子 composable。
- [x] 前端不再出现 composable 直接 `fetch`。
- [x] `core/types.py` 不再混放模型协议与运行时状态。
- [ ] 现有 API、SSE 帧格式、前端页面行为保持兼容。

---

## 8. 备注 (Why This Card, Not TASK-080)

这张卡的出发点不是“目录理论正确性”，而是“哪几个中心文件已经开始阻碍演进”。

先拆运行时边界，再谈目录纯化。  
先消灭真实中心化，再追求九层命名整齐。
