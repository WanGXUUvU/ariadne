# TASK-040 - 多 Agent 子任务模型

## 目标
设计并实现最小多 agent 子任务模型，让主 agent 可以把独立任务委派给子 agent 并收集结果。

## 产品层
Multi-Agent

## 范围内
- 定义 child run 数据结构
- 主 run 可以创建 child run
- child run 有独立 session state
- 汇总 child result 到 parent trace
- 第一版只支持串行等待

## 范围外
- 真并行调度
- agent marketplace
- 自动复杂任务拆解
- 多进程 worker

## 实现步骤
1. 定义 parent run 和 child run 关系。
2. 新增 child session 创建逻辑。
3. 提供内部 API：`spawn_child_agent(task_description)`。
4. child 完成后生成 summary。
5. parent trace 记录 child start / child result。
6. 写测试确认 parent 和 child 状态隔离。

## 完成标准
- 子 agent 的消息不会污染主 session。
- 主 trace 能看到委派和结果。
- 第一版行为可预测，不做自动无限递归。

## 验证
- `python3 -m unittest backend.tests.test_agent -v`

## Review 检查点
- 是否限制最大 child 数量和深度。
- 是否清楚区分 parent/child session。
- 是否避免过早引入复杂调度系统。

