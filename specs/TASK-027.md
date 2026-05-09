# TASK-027 - Streaming 事件输出

## 目标
让 API 可以流式返回 agent 运行事件，为前端实时体验打基础。

## 产品层
Runtime / API

## 范围内
- 新增 streaming endpoint
- 逐步返回 assistant delta、tool call、tool result、final
- 定义 SSE 或 WebSocket 方案
- 保留普通 `/run` 不变

## 范围外
- 多路并发 streaming 优化
- 前端完整实时 UI
- 音频或多模态

## 实现步骤
1. 选择 SSE 作为第一版方案。
2. 定义 streaming event 格式。
3. 修改 agent run 支持 yield events，或增加包装器。
4. FastAPI endpoint 返回 EventSourceResponse 或等价实现。
5. 写测试确认事件顺序稳定。

## 完成标准
- 客户端能边运行边收到事件。
- 非 streaming API 不受影响。
- tool call 和 final answer 顺序正确。

## 验证
- 用 curl 或浏览器手动观察 SSE。
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- streaming schema 是否复用已有 AgentEvent。
- 断连时是否能安全结束。
- 是否没有把 streaming 和业务逻辑耦死。

