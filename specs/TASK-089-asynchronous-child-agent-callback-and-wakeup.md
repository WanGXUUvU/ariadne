# TASK-089: 子智能体异步执行流与父智能体主动唤醒机制

## 1. 核心任务定义 (Goal)
**目标**：彻底改造多智能体协同机制，将目前“父 Agent 同步阻塞等待/循环轮询子 Agent”的粗暴模式，重构为**“异步派发 -> 父 Agent 挂起释放 -> 子 Agent 后台执行 -> 完成后主动向 Session 追加消息并唤醒父 Agent”**的事件驱动执行流。

---

## 2. 详细设计与范围 (Scope & Design)

### 范围内：
1. **工具契约变更 (Refactor spawn_child_agent)**：
   * 修改 `spawn_child_agent` 工具描述：告知大模型“调用此工具委派后台任务后，主流程会挂起，无需轮询或阻塞等待。当子 Agent 完成时，系统会自动将结果作为输入唤醒您”。
   * 调用 `spawn_child_agent` 后，主运行流不再等待，立刻结束当前 Run 并吐出 `status: waiting_for_child`。
2. **后台异步 Worker 与通知链 (Asynchronous Wakeup)**：
   * 修改 [child_agent_dispatcher.py](file:///Users/wangxu/Documents/AGENT%20Build/agent_prototype/execution/child_agent_dispatcher.py) 中子智能体线程结束时的行为。
   * 当子 Agent 执行完毕（在 `_run_child_worker` 线程内）：
     1. 将子 Agent 的最终 `reply` 作为一条特殊格式的 `ChatMessage(role="user", content="[子智能体 ${agent_name} 的执行报告]: ${reply}")` 插入父 Session 的消息流中。
     2. 向 API 的广播信道发送事件，通知前端主会话已被自动唤醒。
     3. 在后台自动拉起主 Agent，对最新的执行报告消息进行推理，继续生成对用户的最终回复。
3. **前端状态感知与平滑过渡**：
   * 前端收到 `waiting_for_child` 终态后，输入框保持禁用，并在对话流底部渲染一个动效精美的 **“子智能体 [审查员] 正在后台深度处理中...”** 的呼吸态状态栏。
   * 当子 Agent 完成，前端感知到自动被拉起的新 SSE 运行流时，状态栏平滑过渡为正常的消息打字机输出，无需用户手动刷新。

### 范围外：
1. 全局图数据库级别的有向无环图（DAG）工作流编排（仅聚焦于 Session 级的消息触发唤醒）。

---

## 3. 实现指南 (Implementation Guide)

### 用户动作：
1. 用户在对话中发送：“请让‘代码审计员’帮我检查 `main.py`，再根据他的意见修改”。

### 用户会看到：
1. 主 Agent 说了句：“好的，我已把代码审计任务委派给‘代码审计员’。”
2. 输入框进入禁用状态，下方浮现“子智能体正在工作...”的状态栏。
3. **不用手动刷新，不用打字**。几秒后，界面上自动弹出了“代码审计员”返回给主会话的审计报告。
4. 主 Agent 自动开始打字：“根据代码审计员的报告，`main.py` 存在以下安全隐患，我将帮您进行修改...”

### 需要改的层：
*   **后端调度器**：[child_agent_dispatcher.py](file:///Users/wangxu/Documents/AGENT%20Build/agent_prototype/execution/child_agent_dispatcher.py) 增加 Worker 结束后的回调触发，自动调用 `RunService.async_stream_agent` 执行流。
*   **工具层**：修改 `spawn_child_agent` 逻辑，移除 `wait_child_agent` 和 `check_child_status` 的推荐。
*   **前端流状态层**：[useRunStreaming.ts](file:///Users/wangxu/Documents/AGENT%20Build/frontend/src/composables/workspace/useRunStreaming.ts) 能够接受子 Agent 完成并自动唤醒主 Agent 的 SSE 新连接帧。
*   **前端状态组件**：在 [ChatPanel.vue](file:///Users/wangxu/Documents/AGENT%20Build/frontend/src/components/ChatPanel.vue) 渲染子智能体正在运行的呼吸动效状态栏。

---

## 4. 验证方法 (Verification)
*   **集成验证**：派发一个模拟耗时 5 秒的子 Agent，观察主 Agent 运行流是否正常断开（输出 pending 状态栏）；5 秒后，子 Agent 完成，主 Agent 能否在没有用户输入的情况下自动被唤醒、打字输出，并且前后端事件链和数据库存储 100% 正确。
