# TASK-083: 工具批次审批状态机与并行进度闭环收口

## 1. 核心任务定义 (Task Refactoring)
**目标**：对 `TASK-076` 落地后的当前缺口进行统一收口，把“并发工具执行 + progress 流 + 审批恢复”从半闭环状态升级为真正可持续演进的工业级闭环。核心不再把审批视为单个异常，而是把同一轮 assistant 产出的整批 `tool_calls` 视为一个 **tool batch**，要求：
1. **进度回传真正打通**：工具 handler 能真实拿到 `ToolCallContext` 并向主线程投递 `tool_progress`。
2. **Trace 真直播**：前端右侧 TracePanel 不再只等 run 结束后 reload，而是随 SSE `agent_event` 实时更新。
3. **审批批次化**：同一批 `tool_calls` 中，无需审批的工具继续并发执行，需要审批的工具进入 pending queue，用户逐个批准/拒绝，但只有整批都进入终态后，才允许继续下一轮模型。
4. **结果与取消语义收紧**：明确“谁先完成是否先出结果”、协作式取消、审批 event index、批次状态一致性等工程规则。
5. **测试补齐**：为并发、progress、批次审批、取消和前端实时渲染补齐回归测试。

---

## 2. 当前问题总盘点 (Problem Inventory)

### 2.1 Progress 链路只搭了骨架，未真正闭环
1. [backend/tools/registry.py](/Users/wangxu/Documents/AGENT%20Build/backend/tools/registry.py:76) 目前只执行 `tool.handler(**args)`，没有把 `ToolCallContext` 注入 handler。
2. [backend/tools/builtin/search/web_search.py](/Users/wangxu/Documents/AGENT%20Build/backend/tools/builtin/search/web_search.py:29) 虽然支持 `__context__`，但当前大概率永远拿不到。
3. 结果：`tool_progress` 的后半段（queue / SSE / 前端渲染）已经写好，但真正的“工具上报 progress”没有实线接通。

### 2.2 右侧 TracePanel 还不是真正的实时 Trace
1. [frontend/src/composables/workspace/useRunStreaming.ts](/Users/wangxu/Documents/AGENT%20Build/frontend/src/composables/workspace/useRunStreaming.ts:96) 已经把 `agent_event` 塞进 `streamingTimeline`。
2. 但 [useRunStreaming.ts](/Users/wangxu/Documents/AGENT%20Build/frontend/src/composables/workspace/useRunStreaming.ts:142) 只有在 `end` 后才 `getTrace()` 并刷新 `traceRuns`。
3. [frontend/src/components/TracePanel.vue](/Users/wangxu/Documents/AGENT%20Build/frontend/src/components/TracePanel.vue:6) 渲染的是 `runs: TraceRunSummary[]`，不是 live timeline。
4. 结果：消息区时间线可以流动，右侧 Trace 卡片却大概率要等整轮结束后才刷新。

### 2.3 结果事件仍是“整批结束后统一吐”，不是 per-tool 实时收口
1. [backend/execution/runtime/tool_runner.py](/Users/wangxu/Documents/AGENT%20Build/backend/execution/runtime/tool_runner.py:327) 当前要等 `gather_task.result()` 全部结束，才统一发 `tool_result/tool_error`。
2. 结果：A 工具已经完成，用户仍要等 B 工具结束后，才能看到 A 的最终结果。

### 2.4 当前取消是协程层取消，不是底层工具真停
1. [tool_runner.py](/Users/wangxu/Documents/AGENT%20Build/backend/execution/runtime/tool_runner.py:289) 的 `task.cancel()` 只取消外层 async task。
2. 真正的同步工具执行仍在线程池里，见 [tool_runner.py](/Users/wangxu/Documents/AGENT%20Build/backend/execution/runtime/tool_runner.py:233)。
3. 结果：审批、异常、超时发生后，前台虽然不再等待，但线程池里的同步工具可能仍继续运行。

### 2.5 审批模型仍是“单异常 / 单 approval_id / 单次恢复”
1. [tool_runner.py](/Users/wangxu/Documents/AGENT%20Build/backend/execution/runtime/tool_runner.py:287) 发现一个 `ApprovalRequiredException` 就整批暂停，只 yield 一条 `approval_required` 后返回。
2. [backend/execution/resume/service.py](/Users/wangxu/Documents/AGENT%20Build/backend/execution/resume/service.py:55) 一次只恢复一个 `approval_id`。
3. 同一轮 assistant 若返回多个需要审批的工具，当前无法可靠支持“逐个批准 / 拒绝，最终补齐整批 tool results 再继续模型”。

### 2.6 批次内审批 event index 语义不稳
1. [tool_runner.py](/Users/wangxu/Documents/AGENT%20Build/backend/execution/runtime/tool_runner.py:219) 把 `current_index` 快照塞进 `context.extra["current_index"]`。
2. 并发批次里多个审批工具可能共享或竞争同一个快照值。
3. [backend/observation/tool_run_observer.py](/Users/wangxu/Documents/AGENT%20Build/backend/observation/tool_run_observer.py:60) 又把这个值落库为 `approval.event_index`。
4. 结果：审批记录里的 `event_index` 未必代表真实主线程事件顺序。

### 2.7 测试覆盖明显落后于新架构
1. 当前已有的是 registry/pipeline 基础测试，见 [backend/tests/unit/tools/test_tool_pipeline.py](/Users/wangxu/Documents/AGENT%20Build/backend/tests/unit/tools/test_tool_pipeline.py:1) 和 [backend/tests/unit/tools/test_tool_registry.py](/Users/wangxu/Documents/AGENT%20Build/backend/tests/unit/tools/test_tool_registry.py:1)。
2. 缺少针对以下主题的闭环测试：
   * 并发耗时明显小于串行
   * `__context__` 注入成功且 progress 真吐出
   * 审批 / 异常下的批次状态收口
   * 前端 Trace live 更新

---

## 3. 新目标流程 (Target Flow)

### 用户动作
用户发送一条会同时触发多个工具的请求，其中包含：
1. 无需审批的只读/安全工具。
2. 一个或多个需要审批的高风险工具。

### 用户会看到
1. **预检广播**：这一批工具先整体挂出，不再因为其中一个审批工具而阻塞所有无审批工具。
2. **无审批工具直接并发跑**：可立即执行的工具继续并发工作，并实时吐 progress / result。
3. **审批工具排队**：需要审批的工具显示为 pending，用户可以逐个 approve / reject。
4. **批次级收口**：只有这一批 `tool_calls` 全部进入终态（completed / rejected / failed）后，模型才进入下一轮推理。
5. **Trace 真直播**：消息区和右侧 TracePanel 都能看到实时事件流，不必等 run end 才刷新。

### 新数据从哪里产生
1. tool batch 元信息：同一轮 assistant 发出的整批 `tool_calls`。
2. batch item 状态：`ready/running/approval_pending/approved/rejected/completed/failed`。
3. live trace 内存态：未落库前的实时 `agent_event` 增量。

### 新数据要存在哪里
1. `tool_progress` 仍默认为内存 SSE 即时态，是否持久化作为可选策略。
2. tool batch / batch item 状态需要有明确的运行态承载；如需跨刷新恢复，则要有持久化表或可恢复记录。
3. 审批记录必须能映射到具体 batch item，而不是只映射到单次恢复入口。

### 前端调哪个接口 / need 改的层
1. `/run/stream`：继续承载 live progress / result / approval 事件。
2. `/approvals/*`：从“单 approval 恢复单工具”升级为“驱动 batch item 状态变化”。
3. 前后端都要新增“当前轮 tool batch 尚未完成”的中间态感知。

---

## 4. 范围内 / 范围外

### 范围内
1. 打通 `ToolCallContext -> ToolRegistry -> handler` 的 progress 注入链。
2. 建立 tool batch / batch item 状态机设计与最小实现。
3. 支持同一轮多 tool call 的“无审批先跑 + 审批逐个决策 + 整批收口后再进模型”。
4. 前端 TracePanel 改为真正的 live trace。
5. 明确结果实时策略、取消策略、审批恢复策略。
6. 补齐并发 / progress / 审批批次 / 前端 live trace 测试。

### 范围外
1. 批量审批 UI 复杂交互（如拖拽排序、批量选择）。
2. 审批策略产品化配置中心重构。
3. 持久化所有 progress 全日志。
4. 把线程池取消彻底升级为 subprocess kill 体系（可先做协作式取消）。

---

## 5. 最小闭环切片 (Slices)

### 🟢 切片 1：Progress 真闭环接通
*   **修改**：[backend/tools/registry.py](/Users/wangxu/Documents/AGENT%20Build/backend/tools/registry.py) / [backend/execution/runtime/tool_runner.py](/Users/wangxu/Documents/AGENT%20Build/backend/execution/runtime/tool_runner.py) / [backend/execution/resume/service.py](/Users/wangxu/Documents/AGENT%20Build/backend/execution/resume/service.py)
*   **实现**：
    *   为 `execute_tool_call()` 增加可选 `context` 入参。
    *   仅在 handler 支持时注入 `__context__`，避免破坏旧工具签名。
    *   恢复流 `resume_run()` 同样支持上下文注入，保证审批后执行的工具也能吐 progress。

### 🟢 切片 2：右侧 TracePanel 改为 Live Trace
*   **修改**：[frontend/src/composables/workspace/useRunStreaming.ts](/Users/wangxu/Documents/AGENT%20Build/frontend/src/composables/workspace/useRunStreaming.ts) / [frontend/src/components/TracePanel.vue](/Users/wangxu/Documents/AGENT%20Build/frontend/src/components/TracePanel.vue)
*   **实现**：
    *   引入 `liveTraceRuns` 或等价内存态。
    *   收到每个 `agent_event` 时同步更新当前 run 的右侧 Trace 数据。
    *   run 结束后再以持久化 `traceRuns` 覆盖 live 态，防止刷新丢失最终事实数据。

### 🟢 切片 3：Tool Batch 状态机建模
*   **修改**：运行时类型层 [NEW]，以及 [backend/execution/runtime/tool_runner.py](/Users/wangxu/Documents/AGENT%20Build/backend/execution/runtime/tool_runner.py)
*   **实现**：
    *   定义 `ToolBatch` / `ToolBatchItem` 运行态结构。
    *   明确 item 状态最少包含：`ready/running/approval_pending/completed/rejected/failed`。
    *   把“审批”从异常语义升级为 batch item 状态语义。

### 🟢 切片 4：预检 + 无审批先跑 + 审批排队
*   **修改**：[tool_runner.py](/Users/wangxu/Documents/AGENT%20Build/backend/execution/runtime/tool_runner.py) / 审批中间件 / observer
*   **实现**：
    *   先预检整批 `tool_calls` 哪些需要审批。
    *   无审批工具直接并发执行。
    *   需要审批的工具生成 pending item，并向前端发队列状态事件。
    *   取消“发现一个审批就整批 return”的旧逻辑。

### 🟢 切片 5：审批恢复改为驱动 Batch Item，而不是直接恢复模型
*   **修改**：[backend/execution/resume/service.py](/Users/wangxu/Documents/AGENT%20Build/backend/execution/resume/service.py) / approval store / approval routes
*   **实现**：
    *   approve / reject 只改变某个 batch item 的状态。
    *   approve 后执行对应工具，reject 后生成对应 tool result 替代物。
    *   只有当整批 item 全部进入终态后，才统一回填所有 `tool_messages` 并继续模型。

### 🟢 切片 6：结果实时策略与协作式取消收紧
*   **修改**：[tool_runner.py](/Users/wangxu/Documents/AGENT%20Build/backend/execution/runtime/tool_runner.py) / `ToolCallContext`
*   **实现**：
    *   决定是否采用 `result_queue` / `asyncio.as_completed()` 让单工具结果实时落前端。
    *   为长耗时工具增加协作式取消信号，至少让工具能在关键阶段主动检查并停止。
    *   清理当前基于 `current_index` 快照的审批 index 语义，改为主线程正式编号或直接以 `tool_call_id` 为主锚点。

### 🟢 切片 7：测试补齐
*   **修改**：`backend/tests/...` / `frontend` 对应测试文件
*   **实现**：
    *   并发耗时测试。
    *   `__context__` 注入与 progress 流测试。
    *   多审批工具同批次的 pending / approve / reject / resume 流测试。
    *   协作式取消测试。
    *   前端 live trace 更新测试。

---

## 6. 工程约束 (Rules)

1. **同一轮 assistant 发出的整批 `tool_calls`，必须全部进入终态后，才能继续下一轮模型。**
2. **tool_result 回填必须严格按 `tool_call_id` 一一对应，不允许丢项。**
3. **审批通过 / 拒绝只是 batch item 状态变化，不应直接驱动模型恢复。**
4. **Live Trace 与持久化 Trace 要分层：前者服务即时感知，后者服务历史事实。**
5. **所有长耗时工具若接入 progress，必须接受统一 context 注入约束。**

---

## 7. 验证与回归单测
*   **后端**
    1. 两个无审批工具并发运行，总耗时显著小于串行。
    2. handler 能真实收到 `__context__` 并吐出 `tool_progress`。
    3. 同一批中“一个无审批 + 两个待审批”时，无审批工具先完成，审批工具进入 pending queue。
    4. 两个待审批工具逐个 approve / reject 后，只有整批全部终态才继续模型。
    5. 协作式取消信号能够让长耗时工具主动退出。
*   **前端**
    1. 右侧 TracePanel 在 run 未结束时就能显示新增 progress / result / approval 事件。
    2. run 结束后 live trace 能与持久化 trace 正确收口，不出现重复事件。

---

## 8. 预期产出
1. 一套真正闭环的 progress 注入链。
2. 一套支持“无审批先跑、审批逐个决策、整批收口再继续模型”的 tool batch 状态机。
3. 一套真实可用的 live trace 前端体验。
4. 一组覆盖并发、审批、取消与实时渲染的回归测试。
