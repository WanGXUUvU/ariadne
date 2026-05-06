# TASK-022 - 前端规划任务卡

## 目标
在正式写 UI 前，确定前端最小产品范围和接口契约，避免前端和后端互相返工。

## 产品层
Frontend Planning

## 范围内
- 确认页面结构
- 确认需要的后端 API
- 确认 session、message、trace 的前端数据模型
- 生成后续 UI 任务卡

## 范围外
- 实现 UI
- 设计系统
- 登录注册

## 实现步骤
1. 列出首版 UI 页面：Chat、Sessions、Trace。
2. 对照当前 API，标记缺口。
3. 定义前端需要的数据类型。
4. 把 UI 实现拆到后续任务卡。
5. 更新 `BUILD_PLAN.md` 中 UI 阶段。

## 完成标准
- 前端第一版范围清楚。
- 每个页面需要什么 API 清楚。
- 可以进入 UI 基础壳实现。

## 结论

### 第一版页面范围
- Chat：发送消息、展示当前会话消息、展示本轮 reply 和事件摘要。
- Sessions：展示会话列表、支持切换当前会话、提供“新建会话”入口。
- Trace：查看某个 session 的历史 runs 和单轮 events。

### 页面与 API 对照
- Chat
  - `POST /run`
  - `GET /sessions/{session_id}`
- Sessions
  - `GET /sessions`
  - 缺口：`POST /sessions`
- Trace
  - `GET /sessions/{session_id}/trace`

### 前端最小数据模型
- SessionSummary：`session_id`、`session_name`、`updated_at`、`last_agent_name`、`last_skill_name`、`message_count`、`last_reply_preview`
- SessionDetail：在 `SessionSummary` 基础上增加完整 `state`
- RunTrace：`run_id`、`user_input`、`reply`、`event_count`、`created_at`、`finished_at`、`events`
- RunOutput：`reply`、`state`、`events`、`metadata`

### 已确认缺口
- 需要独立的 `POST /sessions`，让前端先创建空白会话，再发送第一条消息。
- `POST /sessions` 已拆到 `TASK-023`，不在本卡内实现。

### 后续任务拆分
- `TASK-023`：新建 Session 接口
- 后续新增 UI 基础壳任务卡：布局、路由、API client、最小状态管理
- 后续新增 Chat 主链路任务卡：发送消息、展示 reply/state、基础错误态
- 后续新增 Sessions / Trace 任务卡：会话切换、trace 查看

## 验证
- 仅 Review。

## Review 检查点
- UI 范围是否过大。
- 是否基于已有 API，而不是幻想完整后端。
- 是否保留 trace 作为核心差异点。
