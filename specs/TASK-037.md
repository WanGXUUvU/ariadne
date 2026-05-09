# TASK-037 - 后台任务表

## 目标
为长时间运行的 agent 请求建立后台任务记录，让运行状态可以被查询。

## 产品层
Task Runtime / Observability

## 范围内
- 新增 task/run record 数据模型
- 字段包含 `run_id`、`session_id`、`status`、`started_at`、`finished_at`
- `/run` 时创建记录
- 完成或失败时更新状态
- 提供按 session 查询 runs 的接口

## 范围外
- 真正异步执行
- 队列系统
- worker 进程

## 实现步骤
1. 新增 ORM model 和 Alembic migration。
2. 在 service 层包装 agent run。
3. run 开始写 `running`。
4. run 成功写 `completed`，异常写 `failed`。
5. 新增查询 API 和测试。

## 完成标准
- 每次 `/run` 都有 run record。
- 失败也能被记录。
- 查询接口能看到历史 runs。

## 验证
- `alembic upgrade head`
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- run 状态是否枚举清晰。
- 异常路径是否也更新状态。
- 是否和 session trace 能关联。

