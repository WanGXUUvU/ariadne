# TASK-087: 用户历史消息原地编辑与会话历史截获重发 (方案 A)

## 1. 核心任务定义 (Goal)
**目标**：允许用户在当前会话中对任意历史已发送的“用户消息”进行编辑修改，并在提交后截断该消息之后的全部历史记录，以此新消息为起点重新触发智能体运转。

---

## 2. 详细设计与范围 (Scope & Design)

### 范围内：
1. **前端历史消息编辑 UI**：
   * 在 [MessageList.vue](file:///Users/wangxu/Documents/AGENT%20Build/frontend/src/components/MessageList.vue) 中，当鼠标 Hover 到历史中的 `user` 类型消息时，浮现 **【编辑】(✏️)** 按钮。
   * 点击编辑后，该条消息转化为内联 Textarea 文本框，带有 **【保存并重新提交 / Save & Submit】** 和 **【取消 / Cancel】** 按钮。
2. **历史截断与状态回滚**：
   * 提交编辑时，前端会发出指令，将该会话中**该条消息之后的所有消息和执行 Trace 物理删除（截断）**。
   * 原消息内容替换为编辑后的新文本。
3. **接口支持**：
   * 后端在 `session_service` / `session_store` 中实现 `truncate_session(session_id, message_index)` 接口，删除指定 index 之后的全部 `ChatMessage` 记录及相关的 `Run` 数据。
   * 提供 API Endpoint `POST /api/sessions/{id}/truncate` 接收截断请求。
4. **重新触发执行**：
   * 截断并保存后，自动触发重新运行逻辑，向后端发起新的 `/run/stream` 请求。

### 范围外：
1. 派生多分支会话（此任务保持在当前会话单链条中截断，分支派生属于 TASK-088）。

---

## 3. 实现指南 (Implementation Guide)

### 用户动作：
1. 用户回滚到对话第 2 轮，点击编辑，将“用 Python 读取 a.txt”改为“用 Python 读取 b.txt”。
2. 用户点击“保存并重发”。

### 用户会看到：
1. 对话流第 2 轮之后的所有 AI 回答、工具调用卡片瞬间消失。
2. 对话在第 2 轮以“用 Python 读取 b.txt”为输入重新流动，AI 重新输出。

### 需要改的层：
*   **后端 API 路由层**：在 `agent_prototype/api/` 中增加 `/sessions/{id}/truncate` 路由。
*   **后端持久化层**：在 `SqliteSessionStore` 增加 `truncate_messages(session_id, index)` 物理删除方法。
*   **前端组件层**：[MessageList.vue](file:///Users/wangxu/Documents/AGENT%20Build/frontend/src/components/MessageList.vue) 增加编辑态、保存动作。
*   **前端逻辑层**：[useWorkspace.ts](file:///Users/wangxu/Documents/AGENT%20Build/frontend/src/composables/useWorkspace.ts) 增加调用截断 API 及重新拉起运行的方法。

---

## 4. 验证方法 (Verification)
*   **单元测试**：编写 `test_session_truncate.py`，验证往 session 存入 5 条消息后调用截断（保留前 2 条），数据库中是否仅存前 2 条，且序号保持一致。
*   **手动验证**：在 Web 界面发起多轮对话并使用工具，修改其中一步并提交，确认后续所有卡片与 Trace 全部被清除，且 AI 按新语义执行并成功产生结果。
