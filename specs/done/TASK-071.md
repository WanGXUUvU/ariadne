# TASK-071 - Stop 打断时工具调用状态回写 cancelled

## 背景

用户点击 Stop 按钮后，`finalize_run_service()` 已将 `session_runs.status` 更新为 `cancelled`，
但 `tool_call_records` 表中正在执行的工具记录状态仍停留在 `running`，不会被更新。

## 问题

Trace 回放时，被 Stop 打断的工具调用显示为 `running` 而非 `cancelled`，状态不准确。

## 要做的事

在 `finalize_run_service()` 中，除了更新 run 状态，还要把该 `run_id` 下所有 `status=running` 的 `tool_call_records` 批量更新为 `status=cancelled`。

### 需要改的层

- `storage/stores/session_store.py`：新增方法 `cancel_running_tool_calls(run_id)`，把该 run 下所有 `running` 的 tool_call_records 更新为 `cancelled`
- `application/run_service.py`：在 `finalize_run_service()` 里调用上面的新方法

## Done Conditions

- Stop 后，`tool_call_records` 里被打断的记录状态变为 `cancelled`
- 正常完成的工具调用不受影响，状态仍为 `completed`
