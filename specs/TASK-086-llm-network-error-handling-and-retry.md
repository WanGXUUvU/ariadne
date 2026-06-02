# TASK-086: 大模型网络与 API 错误弹性重试及前端恢复机制

## 1. 核心任务定义 (Goal)
**目标**：提升系统网络鲁棒性，使大模型 API 出现抖动、限流或超时中断时，后端能够自动重试，前端能够优雅展示错误并提供一键重试（断点继续）按钮。

---

## 2. 详细设计与范围 (Scope & Design)

### 范围内：
1. **后端 API 弹性重试机制**：
   * 在 [chat_completions.py](file:///Users/wangxu/Documents/AGENT%20Build/agent_prototype/core/adapters/chat_completions.py) 中，针对 `generate` 和 `async_stream_generate` 引入可配置的指数退避重试（Exponential Backoff Retry）。
   * 自动捕获特定重试类型：网络连接超时、DNS 解析失败、HTTP 状态码 429（限流）、5xx（服务端错误）。
   * 最大重试次数默认为 3 次，初始等待 1s，按指数增加。
2. **前端错误状态捕获与展示**：
   * 前端 [useRunStreaming.ts](file:///Users/wangxu/Documents/AGENT%20Build/frontend/src/composables/workspace/useRunStreaming.ts) 捕获 SSE 连接异常断开、或后端返回的 500 错误帧。
   * 当检测到连接异常中断且未正常 `end` 时，将状态置为 `network_error`。
   * 在聊天消息区底部，渲染一个设计精美的“网络连接中断 / API 调用失败”的卡片，展示具体错误原因。
3. **前端断点恢复 (Retry Button)**：
   * 错误卡片上提供 **【重新连接 / Retry】** 按钮。
   * 点击后，重新向后端发起 `/run/stream`（传入相同的最后一条用户指令，或直接恢复最后一个未完成的执行流）。

### 范围外：
1. 全自动无感知重连（需前端复杂状态对齐，此处以“用户手动点击重试”为主）。

---

## 3. 实现指南 (Implementation Guide)

### 用户动作：
1. 用户在对话过程中遭遇网络断开或 API 节点限流。
2. 用户看到界面底部的网络错误卡片，点击 **【Retry】**。

### 用户会看到：
1. 对话流中止，并淡入红色渐变微光提示卡片：“API Request Timeout (Retry Attempt 3 Failed)”。
2. 点击 **【Retry】** 后，卡片消失，大模型重新开始流式打字并继续输出。

### 调哪个接口 / 需要改的层：
*   **后端 API 适配层**：[chat_completions.py](file:///Users/wangxu/Documents/AGENT%20Build/agent_prototype/core/adapters/chat_completions.py) 增加 retry helper 装饰器或逻辑。
*   **前端流控制组合式函数**：[useRunStreaming.ts](file:///Users/wangxu/Documents/AGENT%20Build/frontend/src/composables/workspace/useRunStreaming.ts) 处理 error 事件和触发 retry。
*   **前端聊天控制面板**：[ChatPanel.vue](file:///Users/wangxu/Documents/AGENT%20Build/frontend/src/components/ChatPanel.vue) 和 [MessageList.vue](file:///Users/wangxu/Documents/AGENT%20Build/frontend/src/components/MessageList.vue) 渲染错误卡片与重试按钮。

---

## 4. 验证方法 (Verification)
*   **模拟测试**：通过临时修改适配器 base_url 指向无效 IP，验证前端是否出现错误卡片；点击重试并还原 IP，验证是否能继续输出。
*   **单元测试**：编写 `test_network_retry.py`，Mock 网络抖动（前 2 次失败，第 3 次成功），验证适配器自动愈合并返回正确内容。
