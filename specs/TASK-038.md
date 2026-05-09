# TASK-038 - 停止和取消运行

## 目标
提供最小取消机制，为后续 UI 的 stop 按钮和 CLI `/stop` 命令打基础。

## 产品层
Task Runtime

## 范围内
- run record 支持 `cancel_requested`
- 新增 cancel API
- agent 主循环在安全点检查取消状态
- 被取消时返回 `cancelled` 事件

## 范围外
- 强杀线程或进程
- 分布式任务队列
- 取消外部正在执行的不可中断请求

## 实现步骤
1. 扩展 run record 字段。
2. 新增 `/runs/{run_id}/cancel`。
3. 在每轮 LLM 调用和工具调用前检查 cancel 标记。
4. 标记取消后停止后续步骤。
5. 测试取消状态转换。

## 完成标准
- 已请求取消的 run 不再继续进入下一步。
- trace 中有取消事件。
- cancel API 对已完成任务返回清晰状态。

## 验证
- 单元测试覆盖 running、completed、missing run。
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- 是否只在安全点取消。
- 状态流是否简单。
- 是否没有假装能取消所有外部请求。

