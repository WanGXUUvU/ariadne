# TASK-002

## Goal
为当前 agent 原型加入会话隔离与重置能力，避免全局 `Agent` 导致不同请求串话。

## In Scope
- `/run` 接收 `session_id`
- 使用内存 session store 保存每个会话的 `AgentState`
- 同一 `session_id` 复用历史状态，不同 `session_id` 彼此隔离
- 增加一个 reset 接口或等价能力，用于清空某个会话
- 更新测试，覆盖多会话隔离和 reset 行为

## Out of Scope
- 持久化数据库
- 多机共享会话
- 鉴权与权限系统
- 多 Agent 编排

## Done when
- 不同 `session_id` 的请求不会共享消息历史
- 同一 `session_id` 能继续上一轮上下文
- 可以清空指定会话并重新开始
- 测试能覆盖隔离与 reset 的核心行为

