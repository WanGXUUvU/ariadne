# TASK-023 - 新建 Session 接口

## 目标
补一个独立的新建 session 接口，让前端可以先创建空白会话，再进入聊天，而不是把“创建会话”和“发送第一条消息”绑在一起。

## 产品层
API

## 范围内
- 新增 `POST /sessions`
- 生成新 `session_id`
- 初始化空 `state`
- 返回新 session 的基础信息
- 补最小测试

## 范围外
- 会话重命名
- 会话删除
- 前端 UI
- 会话模板

## 实现步骤
1. 定义创建 session 的 request/response schema。
2. 在 route 层新增 `POST /sessions`。
3. 在 service/store 层复用现有 session 持久化能力创建空快照。
4. 返回 `SessionSummary` 或等价最小响应。
5. 补 API 测试。

## 完成标准
- 前端不发第一条消息也能先拿到一个合法 session。
- 新 session 能在 `GET /sessions` 里出现。
- 后续 `POST /run` 可以直接复用这个 session。

## 验证
- `python3 -m unittest backend.tests.test_agent -v`

## Review 检查点
- 是否没有把创建 session 和首次运行耦合。
- 返回结构是否复用现有 session 模型。
- 是否没有复制已有持久化逻辑。
