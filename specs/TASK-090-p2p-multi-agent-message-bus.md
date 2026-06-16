# TASK-090: 多智能体点对点消息总线设计与平级通信机制 (P2P Message Bus)

## 1. 核心任务定义 (Goal)
**目标**：为系统引入平级智能体通信机制。打破当前只能由“父智能体派发与等待”的树状局限，构建一套点对点（P2P）消息总线，允许任意两个并行运转的 Agent 在运行过程中通过工具互发消息、查询收件箱，实现网状协同。

---

## 2. 详细设计与范围 (Scope & Design)

### 范围内：
1. **消息信箱表设计 (P2P Message Store)**：
   * 创建数据库表 `agent_messages`：
     * `id`: 消息唯一主键 (UUID)
     * `session_id`: 所属会话 ID
     * `sender_agent_id` / `sender_run_id`: 发送方标识
     * `receiver_agent_id` / `receiver_run_id`: 接收方标识（支持广播，如 "all"）
     * `content`: 消息文本/JSON负载
     * `status`: 状态 (`unread`, `read`)
     * `created_at`: 创建时间
2. **平级通信工具对注册 (Communication Tools)**：
   * 注册 `send_agent_message` 工具：
     * 入参：`receiver_id` (接收方 ID / 职称)，`content` (消息内容)
     * 行为：向消息表写入一条未读消息。
   * 注册 `check_agent_inbox` 工具：
     * 行为：拉取当前 Agent `run_id` 对应的所有未读消息，返回其列表，并将数据库状态标记为 `read`。
3. **点对点协作的运行期感知**：
   * 当 Agent A 向 Agent B 发送消息时，若 Agent B 处于挂起等待状态，消息总线能够根据 `session_id` 自动唤醒 Agent B 的推理流。
4. **前端 Trace 可视化**：
   * 在 TracePanel 中，新增一个 **“信箱/Agent通信流”** 的监控图谱。
   * 实时流式渲染如 `[数据分析师] -> 发送消息 -> [图表生成器]: "请帮我绘制昨日 CPU 趋势图"` 的消息传送动效。

### 范围外：
1. 跨进程/跨机器的网络多 Agent 通信（目前限在本地 SQLite 数据库共享的同一个 Session 内）。

---

## 3. 实现指南 (Implementation Guide)

### 用户动作：
1. 用户要求主 Agent ：“请让‘代码审计员’帮我查错，并让‘安全专家’针对审计员的报错出具一份加固报告”。

### 用户会看到：
1. 主 Agent 委派任务后。
2. 两个子 Agent 在后台自动开始协同：
   * 审计员跑完发现漏洞，调用 `send_agent_message` 将漏洞清单发给安全专家。
   * 安全专家收到唤醒，读取信箱，生成加固方案。
   * 安全专家最终将成果汇合并汇报给主 Agent。
3. 用户在 Trace 视图看到它们内部交互的对话线。

### 需要改的层：
*   **数据库层**：Alembic 迁移新增 `agent_messages` 表。
*   **工具层**：新增 `send_agent_message` 和 `check_agent_inbox` 工具实现。
*   **执行层**：[agent_runtime.py](file:///Users/wangxu/Documents/AGENT%20Build/backend/execution/runtime/agent_runtime.py) 能够在接收到新 P2P 消息时触发挂起 Agent 的唤醒逻辑。
*   **前端 Trace 层**：[TracePanel.vue](file:///Users/wangxu/Documents/AGENT%20Build/frontend/src/components/TracePanel.vue) 支持多 Agent 消息流向关系的拓扑与渲染。

---

## 4. 验证方法 (Verification)
*   **单元测试**：编写 `test_agent_p2p.py`，注册两个 mock agent（A 和 B），验证 A 调用发送工具后，B 的收件箱是否能查到消息；B 处理并回复后，A 再次能读到回复。
