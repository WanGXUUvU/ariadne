# TASK-028 - Streaming 前端接入

## 目标
把 Web UI 的消息发送从同步 `/run` 改为对接 `/run/stream` SSE 接口，实现实时事件流体验。

## 产品线
聊天助理

## 依赖
- TASK-027 Streaming 后端 SSE 已完成

## 范围内
- 前端改用 `fetch + ReadableStream` 接收 SSE（不用 EventSource，因为需要 POST body）
- 接收混合帧：`agent_event` 实时更新 Trace 面板，`delta` 逐字追加 assistant 气泡，`end` 锁定最终 reply
- tool call / tool result / tool error 事件在 Trace 面板实时显示
- 流式结束时用 `end.reply` 替换累积的 delta 内容，保证最终态一致
- 连接失败、服务端 `error` 帧、流提前关闭时显示明确错误提示

## 范围外
- 断线重连自动恢复
- 多路并发 streaming
- 音频/多模态
- token 级光标动画等纯 UI 特效

## 实现步骤
1. 确认后端 SSE 事件格式（开始、assistant/tool 事件、结束、error）。
2. 封装 `streamRun(sessionId, input)` 前端函数。
3. 用 `EventSource` 或 `fetch ReadableStream` 接收事件。
4. 在消息列表中按事件类型追加或更新 assistant 内容。
5. 流式结束后固化最终 reply 并同步 Trace 面板。
6. 处理网络错误、服务端错误和 `error` 事件类型。

## 完成标准
- 发送消息后立即看到运行过程事件出现，不再等待全部完成。
- tool call 发生时 Trace 面板实时显示。
- 页面刷新后历史消息仍可读取。

## 验证
- 手动发送一条触发工具调用的消息，观察 streaming 和 trace 实时更新。
- 前端构建命令通过。

## Review 检查点
- 是否复用已有 AgentEvent schema。
- 断流时 UI 状态是否稳定。
- 是否没有把 SSE 逻辑散落在多个组件。
