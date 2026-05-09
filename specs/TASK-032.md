# TASK-032 - Session fork / resume / new

## 目标
支持从一个已有 session 派生新 session，并能恢复已有 session，让会话管理更接近真实 agent 产品。

## 产品层
Session Control

## 范围内
- 新增 `fork_session`
- 新增 `resume_session` 或读取已有 session 的清晰 API
- 新增 `new_session`
- 记录 parent session id
- fork 后复制 state，但后续互不影响

## 范围外
- 分支可视化 UI
- 自动合并分支
- 多 agent 协作

## 实现步骤
1. 给 session metadata 增加 `parent_session_id`。
2. 实现新建空 session。
3. 实现 fork：复制 state_json 到新 session。
4. 实现 resume：读取已有 session 并返回 metadata。
5. 写测试确认 fork 后两个 session 独立。

## 完成标准
- 用户可以从任意 session fork 新 session。
- fork 后 parent 和 child 的消息互不污染。
- session 列表能看到 parent 信息。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- fork 是否复制必要字段但不复制运行中状态。
- parent id 是否允许为空。
- API 命名是否清晰。

