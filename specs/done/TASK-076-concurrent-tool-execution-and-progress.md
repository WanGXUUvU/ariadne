# TASK-076: 并发工具执行与长耗时渐进进度流

## 1. 核心任务定义 (Task Refactoring)
**目标**：在维持现有 L2 级安全沙箱与审批拦截中间件管道（`BaseMiddleware` / `MiddlewarePipeline`）地基的基础上，使用健壮的 `asyncio.gather` 实现多工具并发调用，防止发生孤儿协程泄漏。同时引入极简的“上下文回调”机制，支持长耗时工具（如网页爬取、复杂检索）的流式进度展示，并完成前端 Trace 卡片内状态日志的微动画实时渲染。

---

## 2. 最小闭环拆解 (Minimal Loop)

### 用户动作
用户发送一条同时触发多个工具的指令，例如：“同时帮我抓取 https://example.com 并查询当前目录下的文件列表”。

### 用户会看到
1. **并发响应**：网页抓取和目录查询的工具卡片在 Trace 面板上**同时**亮起（不再是串行等待）。
2. **渐进进度**：对于耗时长的抓取工具，其卡片内部实时展示逐步推进的进度状态日志（例如：“正在建立连接...” -> “正在下载 HTML...” -> “完成清洗”）。
3. **流畅收口**：两个工具并发结束后，结果实时渲染，AI 进行最终汇总回复。
4. **异常自愈**：若其中一个工具被审批拦截或运行出错，其他运行中的并发工具能被安全取消，防资源泄露；已成功的部分结果正常吐出。

### 新数据从哪里产生
*   并发状态与异常取消由 `tool_runner.py` 中的并发 Task 协同产生。
*   工具进度由工具 Handler 内部在不同执行阶段主动触发 `context.emit_progress` 产生。

### 新数据要存在哪里
*   `tool_progress` 进度流属于“即时交互状态数据”，仅通过内存 SSE 流推送到前端，**不落库**以保持轻量级。
*   最终工具完成的 `ToolResult` 依然通过原有机制落库持久化。

### 前端调哪个接口
*   `/run/stream`（SSE 接口），用于接收新增的 `tool_progress` 类型的 `AgentEvent`。

### need改的层 (基于重构后的 L1-L9 最新分层)
1.  **领域类型层**：[types.py](file:///Users/wangxu/Documents/AGENT%20Build/backend/execution/runtime/types.py) 中新增 `tool_progress` 类型的 `AgentEvent` 放行。
2.  **安全中间件层**：[base.py](file:///Users/wangxu/Documents/AGENT%20Build/backend/security/middleware/base.py) 中的 `ToolCallContext` 支持传入 `on_progress` 回调，挂载 `emit_progress`便捷入口。
3.  **运行时执行引擎**：[tool_runner.py](file:///Users/wangxu/Documents/AGENT%20Build/backend/execution/runtime/tool_runner.py)
    *   重构 `async_handle_tool_calls`，将串行循环升级为基于 `asyncio.gather` 的并发调度。
    *   在协程包装器内，封锁进度回调函数，并注入至工具的 `ToolCallContext`，捕获进度事件并 `yield`。
    *   在发生审批拦截或未知异常时，对其他并发中的协程调用 `cancel()` 进行安全回收，实现异常自愈。
4.  **流式问答编排层**：[stream_run_session.py](file:///Users/wangxu/Documents/AGENT%20Build/backend/execution/streaming/stream_run_session.py) 适配新增的 `tool_progress` 帧，以 SSE 流刷向前端。
5.  **前端界面与类型适配**：
    *   [index.ts](file:///Users/wangxu/Documents/AGENT%20Build/frontend/src/types/index.ts) 放行 `tool_progress` 类型定义。
    *   [TracePanel.vue](file:///Users/wangxu/Documents/AGENT%20Build/frontend/src/components/TracePanel.vue) 实时拦截进度事件，并将进度日志无缝更新至对应的工具卡片。

---

## 3. 切片推进计划 (Slices)

### 🟢 切片 1：数据契约与上下文改造 (DTO & Context Upgrade)
*   **修改**：[types.py](file:///Users/wangxu/Documents/AGENT%20Build/backend/execution/runtime/types.py) / [base.py](file:///Users/wangxu/Documents/AGENT%20Build/backend/security/middleware/base.py)
*   **实现**：
    *   在 `AgentEvent.type` 字面量中放行 `"tool_progress"`。
    *   在 `ToolCallContext` 初始化时，支持可选异步回调 `on_progress`，提供 `async def emit_progress(self, text: str)` 便捷分发方法。

### 🟢 切片 2：长耗时工具 handler 示范改造
*   **修改**：[web_search.py](file:///Users/wangxu/Documents/AGENT%20Build/backend/infrastructure/tools/builtin/web_search.py) (或新增长耗时 Demo 工具)
*   **实现**：
    *   改造工具 Handler 的入参，使其支持通过 `**kwargs` 或特定参数接收 `__context__`。
    *   在 Handler 内部，模拟长耗时并分阶段调用 `__context__.emit_progress("正在...")`，验证回调流。

### 🟢 切片 3：核心并发重构与安全自愈 (Exception & Cancellation Handlings)
*   **修改**：[tool_runner.py](file:///Users/wangxu/Documents/AGENT%20Build/backend/execution/runtime/tool_runner.py)
*   **实现**：
    *   用 `asyncio.gather` 并发执行封装了 `MiddlewarePipeline` 的各个工具任务。
    *   利用 `asyncio.create_task` 包装子任务，以便在任一协程抛出阻断性异常（如 `ApprovalRequired`）或致命崩溃时，能够主动调用 `task.cancel()` 取消其余正在进行的工具，防止资源泄露。
    *   在分发的协程中，构造绑定了当前 `tool_call_id` 的进度回调函数并注入 Context。
    *   每当工具触发进度回调，立刻构造 `tool_progress` 类型的 `AgentEvent` 并通过生成器 `yield` 出来。

### 🟢 切片 4：SSE 流式会话保活与事件透传
*   **修改**：[stream_run_session.py](file:///Users/wangxu/Documents/AGENT%20Build/backend/execution/streaming/stream_run_session.py)
*   **实现**：
    *   在 SSE 主循环中捕获 `tool_progress` 类型的事件。
    *   将其格式化为 `tool_progress` 形状的 SSE `StreamFrame`，实时推送给前端。

### 🪐 切片 5：前端 Trace 面板进度状态渲染与适配
*   **修改**：[index.ts](file:///Users/wangxu/Documents/AGENT%20Build/frontend/src/types/index.ts) / [TracePanel.vue](file:///Users/wangxu/Documents/AGENT%20Build/frontend/src/components/TracePanel.vue)
*   **实现**：
    *   在前端的 `AgentEvent` 类型中加入 `"tool_progress"` 类型。
    *   在 `TracePanel.vue` 中，当接收到 `tool_progress` 类型的 `agent_event` 时，根据 `tool_call_id` 找到对应的工具执行卡片，将其进度内容动态挂载到该卡片内部（如使用 `sub_status` 或 `logs` 列表），并通过细微的透明度/位移微动画实现流式日志渐进展示。

---

## 4. 验证与回归单测
*   **单测编写**：在 `backend/tests` 下，新增 `test_concurrent_tools.py`。
*   **验证内容**：
    1.  **并发性验证**：验证两个工具并发运行的总耗时是否小于它们串行耗时之和。
    2.  **进度投递验证**：验证长耗时工具的进度回调是否能在流式管道中以正确的 `tool_call_id` 吐出。
    3.  **异常回收验证**：验证当某一个工具抛出异常或审批拦截时，并发的其它协程是否确实收到了 `CancelledError`，确保无孤儿协程泄漏。
