# TASK-088: 会话派生分支多版本探索 (Session Forking Branches - 方案 B)

## 1. 核心任务定义 (Goal)
**目标**：实现会话的派生分支（Fork）机制。当用户编辑修改历史消息时，不破坏原会话的上下文，而是从该截断点派生出一个全新的会话分支继续对话，让用户能够对比和切换不同版本的 Agent 探索轨迹。

---

## 2. 详细设计与范围 (Scope & Design)

### 范围内：
1. **数据模型升级**：
   * Session 表增加 `parent_session_id` 外键，用于记录派生来源。
   * Session 表增加 `fork_message_index`，记录是从父会话的哪条消息（序号）开始派生出来的。
2. **后端派生 API (Fork Session)**：
   * 提供 `POST /api/sessions/{id}/fork` 接口，接收参数：`message_index` (截断点索引)、`new_content` (可选，新编辑的消息内容)。
   * 后端处理逻辑：
     1. 新建一个 Session 实例，复制原 Session 的基础配置（Agent、Model、Workspace 等）。
     2. 将原 Session 中索引从 `0` 到 `message_index - 1` 的所有 `ChatMessage` 深度复制并保存为新 Session 的历史消息。
     3. 如果提供了 `new_content`，将该消息作为新 Session 的第 `message_index` 条消息追加进去。
     4. 关联 `parent_session_id = {id}`，保存入库并返回新 `session_id`。
3. **前端分流唤醒与切换**：
   * 在 [MessageList.vue](file:///Users/wangxu/Documents/AGENT%20Build/frontend/src/components/MessageList.vue) 编辑历史时，增加复选框选项：“派生新分支会话 (Branch into new session)”。
   * 若勾选，点击提交后调用 fork 接口，前端自动切换到新返回的 `session_id`（新会话），并在新会话中流式运行。原会话历史完美保留，不发生任何破坏。
4. **侧边栏分支层级视觉展示**：
   * [SessionSidebar.vue](file:///Users/wangxu/Documents/AGENT%20Build/frontend/src/components/SessionSidebar.vue) 渲染会话时，能够识别并缩进显示子分支会话，或者在卡片上显示“派生自 #xxxxx”的微光 Badge。

### 范围外：
1. 多分支会话的树状拓扑可视化关系图（仅在侧边栏做轻量分级或标识）。

---

## 3. 实现指南 (Implementation Guide)

### 用户动作：
1. 用户在已有会话的第 3 条消息点击编辑，勾选“派生新分支”，修改文本并提交。

### 用户会看到：
1. 界面瞬间切换到一个名为 “Untitled #分支” 的新会话。
2. 历史区域仅展示修改前的那 2 条消息以及刚刚修改好的第 3 条消息。
3. AI 重新输出。
4. 在左侧侧边栏中，原来的会话完好无损，新会话在其下方显示（有分支关联标识）。

### 需要改的层：
*   **数据库迁移层**：Alembic 增加 Session 表 `parent_session_id` / `fork_message_index` 字段迁移。
*   **后端 API 路由层**：在 `agent_prototype/api/` 中增加 `/sessions/{id}/fork` 路由。
*   **后端服务层**：在 `SqliteSessionStore` 增加 `fork_session` 复制逻辑。
*   **前端逻辑层**：[useWorkspace.ts](file:///Users/wangxu/Documents/AGENT%20Build/frontend/src/composables/useWorkspace.ts) 增加调用 fork API 逻辑并切换路由。
*   **前端 UI 组件**：修改 [SessionSidebar.vue](file:///Users/wangxu/Documents/AGENT%20Build/frontend/src/components/SessionSidebar.vue) 支持分支 Badge 或嵌套树展现。

---

## 4. 验证方法 (Verification)
*   **单元测试**：编写 `test_session_fork.py`，验证 Fork 后，对原 session 写入消息不会影响派生的 session，两个 session 的历史完全物理隔离独立演进。
*   **集成测试**：通过接口测试 `/sessions/{id}/fork` 并验证 DB 中 parent 关联完整性。
