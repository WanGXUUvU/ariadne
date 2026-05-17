# TASK-027 - Streaming 后端全链路

## 目标
后端实现完整 SSE streaming：工具调用阶段推语义事件，最终回答阶段推 token 级 delta，为 TASK-028 前端接入提供稳定契约。

## 产品层
Runtime / API

## 范围内
- `ModelAdapter` 新增 `stream_generate()` 抽象方法（token 级）
- `OpenAI adapter` 实现 `stream_generate()`，使用 `stream=True`，yield delta chunk
- `AgentRuntime` 新增 `stream_run()` 生成器：
  - 工具调用阶段：同步执行工具，yield `AgentEvent`（事件级）
  - 最终回答阶段：调 `stream_generate()`，yield delta（token 级）
- `core/schemas.py` 新增 `StreamFrame`（type: start / agent_event / delta / end / error）
- `run_service.py` 新增 `stream_agent_service()`，复用 `_prepare_run_context` 和 `_persist_run_result`
- FastAPI 新增 `POST /run/stream`，返回 `StreamingResponse`（text/event-stream）
- 保留普通 `/run` 不变

## 范围外
- 多路并发 streaming 优化
- 前端完整实时 UI（见 TASK-028）
- 音频或多模态
- WebSocket 方案
- 断线重连

## 实现步骤
1. `core/schemas.py` 新增 `StreamFrame`。
2. `model/adapter.py` 新增 `stream_generate()` 抽象方法。
3. `model/openai_adapter.py` 实现 `stream_generate()`。
4. `runtime/agent_runtime.py` 新增 `stream_run()` 生成器。
5. `application/run_service.py` 新增 `stream_agent_service()`。
6. `api/routes/run_routes.py` 新增 `/run/stream`。
7. 写测试确认事件顺序、delta 输出、错误路径和 `/run` 回归稳定。

## 完成标准
- curl 能观察到：start → agent_event* → delta* → end 的 SSE 帧序列。
- 普通 `/run` 不受影响。
- 断连时服务端安全停止推流，落库按最终态语义处理。

## SSE frame 契约
- endpoint: `POST /run/stream`，请求体复用 `AgentInput`
- 响应类型: `text/event-stream`

### StreamFrame 结构
- `start`: `{ session_id, run_id, agent_name, skill_name }`
- `agent_event`: `{ event: AgentEvent }`（工具调用 / 工具结果 / 工具错误）
- `delta`: `{ content: str }`（最终回答阶段 token 级输出）
- `end`: `{ reply, state, metadata }`
- `error`: `{ code, message }`

## 验证
- 用 curl 手动观察 SSE 帧顺序。
- 相关单测通过。

## Review 检查点
- `stream_run()` 是否只在最终回答轮调 `stream_generate()`，工具轮不调。
- `_prepare_run_context` / `_persist_run_result` 是否被复用，没有重复逻辑。
- streaming 是否只做传输封装，没有把业务逻辑耦死。
- 断连时是否能安全结束。

