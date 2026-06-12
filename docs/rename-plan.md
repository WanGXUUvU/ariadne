# 命名重构计划

> 2026-06-12

---

## 类重命名

| 当前名称 | 改后名称 | 作用 | 修改理由 |
|----------|----------|------|----------|
| `StreamRunSession` | `RunSSEBridge` | 把执行结果翻译成 SSE 帧发给前端 | "Session" 一词三用，实际是协议适配器不是会话 |
| `RunExecutionSession` | `RunLifecycle` | 管理一次 run 的起停、事件收束、异常处理、finalize 调度 | "Session" 一词三用，实际是运行生命周期 |
| `RunExecutionDeps` | `RunLifecycleParams` | 启动一次 run 所需的完整物料包（ctx + agent_runner + persist + 输入参数） | "Deps" 太泛，看不出是"启动参数" |
| `RunExecutionResult` | `RunLifecycleResult` | 生命周期结束时产出的结果（status + reply + events + state + usage） | 跟随 RunLifecycle 命名 |
| `RuntimeContextFactory` | `RunContextFactory` | 为一次 run 装配完整上下文（state + agent_profile + adapter + policy） | Runtime 与 Run 不统一，且多 4 个字母无意义 |
| `RunPersistenceService` | `RunRecorder` | run 终态统一持久化入口（COMPLETED / PAUSED / CANCELLED / FAILED） | Persistence + Service 双重后缀，本质是记录器 |
| `ToolRunObserver` | `ToolTracer` | 工具执行生命周期落库（on_tool_start / on_tool_finish / on_approval_required） | Observer 太泛，实际是 trace 的"写"半边 |
| `ChildAgentDispatcher` | `ChildRunLauncher` | 子 Agent 线程调度、状态查询、回调构造 | Dispatcher 只描述了"分发"，还包含"启动"和"查询" |
| `SqliteSessionStore` | `SessionStore` | session 快照和主记录的持久化访问 | SQLite 是实现细节，不应在接口名中暴露 |
| `SqliteRunStore` | `RunTraceStore` | run trace / tool_call / 事件记录的持久化访问 | SQLite 是实现细节，Run 太泛不够精确 |

---

## 方法重命名

| 当前名称 | 位置 | 改后名称 | 理由 |
|----------|------|----------|------|
| `RunContextFactory.build()` | runtime_context_factory.py | `assemble()` | build 什么？assemble 明确是"装配 RunContext" |
| `RunContextFactory.build_adapter()` | runtime_context_factory.py | `create_adapter()` | 跟 assemble 区分：装小车 vs 造零件 |
| `AgentRunner.run()` | agent_runtime.py | `execute()` | 跟 Lifecycle 的 run/iterate 区分：发动机执行 vs 生命周期迭代 |
| `RunLifecycle.run()` | execution_session.py | `iterate()` | 它是消费 AgentRunner 的流并迭代产出，不是"跑" |
| `RunLifecycle.collect_final_result()` | execution_session.py | `execute()` | 异步消费生命周期项，只拿最终结果 |
| `RunLifecycle.collect_final_result_sync()` | execution_session.py | `execute_sync()` | 同步版本 |
| `RunSSEBridge.run()` | stream_run_session.py | `stream()` | 产出 SSE 帧流，不是"跑" |
| `RunService.run_agent()` | service.py | `run()` | Agent 已在上下文隐含 |
| `RunService.async_stream_agent()` | service.py | `stream()` | 流式入口，与 run() 对称 |
| `RunService._build_agent_runner()` | service.py | `_create_agent_runner()` | 统一 create 动词 |
| `SessionStore.get()` | memory/session/store.py | `load_state()` | get 什么？load_state 明确 |
| `SessionStore.upsert_session_snapshot()` | memory/session/store.py | `save_state()` | upsert 是 DB 术语，对外应叫 save |
| `SessionStore.read_session_record()` | memory/session/store.py | `load_record()` | 统一 load 动词 |
| `SessionStore.read_session_state()` | memory/session/store.py | → 合并到 load_state() | 与 load_state 重复 |
| `ChildRunLauncher.make_child_dispatcher()` | child_agent_dispatcher.py | `create_launcher()` | 统一 create，简化 |
| `ChildRunLauncher.make_status_checker()` | child_agent_dispatcher.py | `create_status_checker()` | 统一 create |
| `ChildRunLauncher.make_child_waiter()` | child_agent_dispatcher.py | `create_waiter()` | 统一 create |
| `ChildRunLauncher._run_child_worker()` | child_agent_dispatcher.py | `_execute_child()` | worker 暗示常驻，实际跑一次 |
| `RunService.finalize_run()` | service.py | `cancel_run()` | 此方法只调 CANCELLED 终态，跟 RunRecorder.finalize_run() 撞名 |

---

## 文件重命名

| 当前路径 | 改后路径 | 理由 |
|----------|----------|------|
| `execution/runtime_context_factory.py` | `execution/run_context_factory.py` | 类名同步 |
| `execution/runtime/execution_session.py` | `execution/runtime/run_lifecycle.py` | 类名同步 |
| `execution/streaming/stream_run_session.py` | `execution/streaming/sse_bridge.py` | 类名同步 |
| `execution/persistence/service.py` | `execution/persistence/run_recorder.py` | 类名同步 |
| `execution/child_agent_dispatcher.py` | `execution/child_run_launcher.py` | 类名同步 |
| `observation/tool_run_observer.py` | `observation/tool_tracer.py` | 类名同步 |
| `memory/session/store.py` | `memory/session/store.py` | 类名改了路径不变 |
| `memory/run/store.py` | `memory/run/store.py` | 类名改了路径不变 |

---

## 改名后三层关系

```
RunSSEBridge（SSE 翻译）
  └── RunLifecycle（生命周期）
        └── AgentRunner（执行引擎）
```

## 改名后一次流式 run 的完整装配流程

```
RunService.stream()
│
├── 1. ctx = RunContextFactory.assemble(agent_input)    ← 装配小推车
├── 2. tracer = ToolTracer(db, ...)                      ← 挂记录仪
├── 3. agent_runner = _create_agent_runner(ctx, ...)     ← 装发动机
│
└── 4. async for frame in RunSSEBridge.stream(...)       ← 点火 + 翻译出去
          │
          └── RunLifecycle.iterate()
                │
                └── AgentRunner.async_stream_run(...)
```
