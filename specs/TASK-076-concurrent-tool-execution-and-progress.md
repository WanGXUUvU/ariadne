# TASK-076: 并发工具执行与长耗时渐进进度流

## 1. 核心任务定义 (Task Refactoring)
**目标**：在维持现有洋葱圈中间件（AOP Sandbox & Approval）地基的基础上，用最朴素、健壮的 `asyncio.gather` 实现多工具并发调用，并引入极简的“工具上下文回调”机制，支持长耗时工具（如网页爬取、复杂 SQL）的流式进度展示。

---

## 2. 最小闭环拆解 (Minimal Loop)

### 用户动作
用户发送一条同时触发多个工具的指令，例如：“同时帮我抓取 https://example.com 并查询当前目录下的文件列表”。

### 用户会看到
1. **并发响应**：网页抓取和目录查询的工具卡片在 Trace 面板上**同时**亮起（不再是串行等待）。
2. **渐进进度**：对于耗时长的抓取工具，其卡片内部实时展示逐步推进的进度状态日志（例如：“正在建立连接...” -> “正在下载 HTML...” -> “完成清洗”）。
3. **流畅收口**：两个工具并发结束后，结果实时渲染，AI 进行最终汇总回复。

### 新数据从哪里产生
*   并发状态由 `async_handle_tool_calls` 中的并发 Task 协同产生。
*   工具进度由工具 Handler 内部在不同执行阶段主动触发 `context.emit_progress` 产生。

### 新数据要存在哪里
*   `tool_progress` 进度流属于“即时交互状态数据”，仅通过内存 SSE 流推送到前端，**不落库**以保持轻量级。
*   最终工具完成的 `ToolResult` 依然通过原有机制落库持久化。

### 前端调哪个接口
*   `/run/stream`（SSE 接口），用于接收新增的 `tool_progress` 帧。

### need改的层
1.  **DTO 数据定义层**：`schemas.py` 中新增 `tool_progress` 类型的 `AgentEvent` 支持。
2.  **运行时上下文车厢**：`ToolCallContext` 中支持注入 `emit_progress` 的回调函数。
3.  **运行时工具执行器**：
    *   重构 `async_handle_tool_calls`，将串行 `for` 循环升级为基于 `asyncio.gather` 的并发调度。
    *   在并发协程内部，封装进度回调函数，并注入至各工具的 `ToolCallContext`。
4.  **流式运行会话服务层**：`stream_run_session.py` 适配新增的进度事件流，将其转为标准的 SSE Frame 实时推出。

---

## 3. 切片推进计划 (Slices)

### 🟢 切片 1：数据契约与上下文改造 (DTO & Context Upgrade)
*   **修改**：`agent_prototype/interface/dto/schemas.py` 或者是 `core/schemas.py`
*   **修改**：`agent_prototype/application/runtime/middleware/base.py` 中的 `ToolCallContext`
*   **实现**：
    *   在 `AgentEvent` 的 `type` 枚举/校验中，放行 `tool_progress` 这一类型。
    *   在 `ToolCallContext` 初始化时，允许传入 `on_progress` 回调，并在 Context 上挂载一个便捷的方法 `async def emit_progress(self, text: str)`。

### 🟢 切片 2：长耗时工具 handler 示范改造
*   **修改**：`agent_prototype/infrastructure/tools/builtin/web_search.py`（或增加一个模拟长耗时的 Demo 工具）
*   **实现**：
    *   改造工具 Handler 的入参，使其支持通过 `**kwargs` 或特定参数接收 `__context__`。
    *   在 Handler 内部，模拟长耗时并分阶段调用 `__context__.emit_progress("正在...")`，验证回调链路。

### 🟢 切片 3：核心并发重构与回调捕获
*   **修改**：`agent_prototype/application/runtime/tool_executor.py` 中的 `async_handle_tool_calls`
*   **实现**：
    *   用 `asyncio.gather` 包装多工具的并发执行任务（保留原有的 Sandbox 和 Approval 中间件管道执行链）。
    *   在分发的协程中，构造绑定了当前 `tool_call_id` 的进度回调函数并注入 Context。
    *   每当工具触发进度回调，立刻构造 `tool_progress` 类型的 `AgentEvent` 并通过生成器 `yield` 出来。

### 🟢 切片 4：SSE 流式会话保活与事件透传
*   **修改**：`agent_prototype/application/runtime/agent_runtime.py` 里的 `async_stream_run`
*   **修改**：`agent_prototype/application/services/run/stream_run_session.py` 里的 `run`
*   **实现**：
    *   在 `async_stream_run` 捕获 `tool_progress` 事件，并向外层继续 `yield`。
    *   在 `stream_run_session.py` 中，拦截 `tool_progress` 事件，构造类型为 `tool_progress` 的 SSE `StreamFrame` 立即发给前端，完成保活与进度展示闭环。

---

## 4. 验证与回归单测
*   **单测编写**：在 `agent_prototype/tests` 下，新增 `test_concurrent_tools.py`。
*   **验证内容**：
    1.  验证两个工具并发运行的总耗时是否小于它们串行耗时之和（证明并发有效）。
    2.  验证长耗时工具的进度回调是否能在流式管道中以正确的 `tool_call_id` 吐出。
    3.  验证当触发审批拦截时，并发的 `paused_for_approval` 机制是否依然能在抛出异常后被优雅拦截并阻断。
