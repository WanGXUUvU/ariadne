# TASK-038 - 异步重构（async stream_run）

## 目标
将 stream_run 链路从同步 generator 改为 async generator，使工具执行阶段可被取消，实现真正的 Stop 中断（含 tool call 执行阶段）。

## 产品层
Runtime / Infrastructure

## 背景
TASK-037 完成了文字流式阶段的 Stop + 截断保存。但工具执行阶段（handle_tool_calls）是同步阻塞的，用户点 Stop 时工具仍会跑完，无法中断。

成熟产品做法：将整条 stream_run 链路改为 async，工具执行变为 `await`，asyncio 事件循环可在客户端断开时触发 CancelledError，在 except 里做 finalize 落库。

## 用户动作
用户在 agent 工具执行过程中点击 Stop 按钮。

## 用户会看到
- 工具执行被中断（不再等工具跑完）
- 截断内容保存，上下文连续（与 TASK-037 行为一致）

## 范围内
- `model/openai_adapter.py`：`stream_generate` 改为 `async def` + `async for`
- `runtime/agent_runtime.py`：`stream_run` 改为 `async def`；`handle_tool_calls` 改为 `async def`
- `application/run_service.py`：`stream_agent_service` 改为 `async def`；在 `CancelledError` 里调 finalize 落库
- `api/routes/run_routes.py`：StreamingResponse 改用 async generator
- 单元测试同步更新（`async def test_` + `asyncio.run` 或 `pytest-asyncio`）

## 范围外
- 前端改动（前端 Stop 逻辑已在 TASK-037 完成）
- 非流式 run_agent_service（保持同步）

## 实现步骤
1. `openai_adapter.py`：`stream_generate` 改 async
2. `agent_runtime.py`：`handle_tool_calls` 改 async；`stream_run` 改 async generator
3. `run_service.py`：`stream_agent_service` 改 async；加 `try/except asyncio.CancelledError` 做 finalize
4. `run_routes.py`：StreamingResponse 使用 async generator
5. 更新受影响的单元测试
6. 全量测试通过

## 完成标准
- 工具执行阶段 Stop → 工具中断 → finalize 落库 → 上下文连续
- 全量测试通过
- 非流式 `/run` 不受影响

## 验证
- `python3 -m unittest discover -s agent_prototype/tests -p 'test_*.py' -v`
- 手动触发工具调用，执行中 Stop，验证中断和落库

## Review 检查点
- CancelledError 处理是否完整（不吞异常）
- async generator 是否正确关闭（aclose）
- 非流式路径是否不受影响
