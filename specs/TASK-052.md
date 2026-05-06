# TASK-052 - Streaming 前端接入

## 目标
把 Web UI 的消息发送从同步 `/run` 改为对接 `/run/stream` SSE 接口，实现字流式输出体验。

## 产品线
聊天助理

## 依赖
- TASK-049 Streaming 后端 SSE 已完成

## 范围内
- 前端改用 EventSource 或 fetch + ReadableStream 接收 SSE
- 消息列表实时追加 delta 内容
- tool call / tool result 事件在 Trace 面板实时更新
- 流式结束时锁定最终 reply
- 连接失败时显示错误提示

## 范围外
- 断线重连自动恢复
- 多路并发 streaming
- 音频/多模态

## 实现步骤
1. 确认后端 SSE 事件格式（delta、tool_call、tool_result、final、error）。
2. 封装 `streamRun(sessionId, input)` 前端函数。
3. 用 `EventSource` 或 `fetch ReadableStream` 接收事件。
4. 在消息列表中逐字追加 assistant 内容。
5. 流式结束后更新 Trace 面板。
6. 处理网络错误和 `error` 事件类型。

## 完成标准
- 发送消息后立即看到文字逐步出现，不再等待全部完成。
- tool call 发生时 Trace 面板实时显示。
- 页面刷新后历史消息仍可读取。

## 验证
- 手动发送一条触发工具调用的消息，观察 streaming 和 trace 实时更新。
- 前端构建命令通过。

## Review 检查点
- 是否复用已有 AgentEvent schema。
- 断流时 UI 状态是否稳定。
- 是否没有把 SSE 逻辑散落在多个组件。
