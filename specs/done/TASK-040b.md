# TASK-040b - 多 Agent 并行调度

## 目标
在 TASK-040 串行基础上，升级为异步并行模式：主 Agent 可以同时启动多个子 Agent，查询各自状态，并在合适时机汇总结果。

## 产品层
Multi-Agent

## 背景
TASK-040 实现了同步阻塞的 spawn_child_agent，子 Agent 返回前主 Agent 完全等待。
本任务将其拆分为 spawn / check / wait 三个原语，让 LLM 自主协调多个并行子任务。

## 范围内
- `spawn_child_agent(task, agent_name?)` 提交子 Agent 到线程池，立刻返回 `child_run_id`
- `check_child_status(child_run_ids[])` 非阻塞查询多个子 Agent 的运行状态和结果
- `wait_child_agent(child_run_id)` 阻塞等待指定子 Agent 完成并返回结果
- run 级别的 `futures` 字典：`{ child_run_id: Future }`，注入三个工具的闭包
- 子 Agent 落库逻辑保持不变（parent_run_id 记录）
- 在 `build_run_registry` 注册三个新工具

## 范围外
- 跨进程 / 跨机器调度
- 子 Agent 流式输出推给前端
- 最大并发数限制（后续任务）
- 子 Agent 指定专属 system_prompt（后续任务）

## 新增工具

### spawn_child_agent（改造）
```
输入：task (str), agent_name? (str)
输出：{ child_run_id: str }   ← 不再包含 content，只返回 ID
行为：把子 Agent 提交到线程池，立刻返回，不等待
```

### check_child_status（新建）
```
输入：child_run_ids (list[str])
输出：{ id: { status: "running"|"done"|"error", result?: str } }
行为：非阻塞，只查 Future 状态，不等待
```

### wait_child_agent（新建）
```
输入：child_run_id (str)
输出：{ result: str }
行为：future.result() 阻塞到完成，超时 120s
```

## 需要改的层

| 文件 | 改动 |
|------|------|
| `tools/builtin/spawn_child_agent.py` | 改为提交线程池，返回 run_id |
| `tools/builtin/check_child_status.py` | 新建，查询 futures 字典 |
| `tools/builtin/wait_child_agent.py` | 新建，future.result() |
| `tools/tool_registry.py` | `build_run_registry` 注册三个工具 |
| `application/run_service.py` | 创建 futures 字典，传入 build_run_registry |

## 实现步骤
1. 定义 `futures` 字典结构，确认注入方式
2. 改造 `spawn_child_agent`：提交线程池，返回 run_id
3. 新建 `check_child_status`
4. 新建 `wait_child_agent`
5. 更新 `build_run_registry` 签名，加入 futures 参数
6. 更新 `run_service.py` 三个 service 函数
7. 写测试：并行启动两个子 Agent，check_status 返回正确状态，wait 返回结果

## 完成标准
- 主 Agent 可同时 spawn 多个子 Agent
- check_child_status 能区分 running / done
- LLM 可以自主决定"先用已完成的结果、继续等未完成的"
- 子 run 的 parent_run_id 仍正确落库
- 原有串行行为（直接 wait）不受影响

## 验证
- `python3 -m unittest agent_prototype.tests.test_parallel_child_agents -v`

## Review 检查点
- futures 字典是否会内存泄漏（run 结束后清理）
- 线程池大小是否需要限制
- wait 超时策略是否合理
