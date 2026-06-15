# 数据库 Schema 文档

> 基于实际 ORM 模型和运行时代码生成，更新时间：2026-06-12

---

## 表关系总览

```
session_records (1) ──< (N) session_runs (1) ──< (N) session_run_events
       │                        │
       │                        └──< (N) tool_call_records
       │
       └──< (N) pending_approvals
```

- 一个会话（session）有多轮运行（run）
- 一轮 run 有多条事件（event）
- 一轮 run 可能有多次工具调用记录（tool_call）
- 一轮 run 可能有多个待审批工单（approval）

---

## 1. `session_records` — 会话主表

一行代表一个独立对话会话。

```
session_records
│
├── session_id
│   ├── 类型：string (PK)
│   ├── 示例："a3f2b1c8d9e4"
│   └── 含义：会话全局唯一标识，创建时由 uuid.uuid4().hex 生成
│
├── session_name
│   ├── 类型：string，可空
│   ├── 示例："我的代码助手"
│   ├── 默认：等于 session_id
│   └── 含义：会话展示名称，用户可在前端侧边栏重命名
│
├── state_json
│   ├── 类型：text (JSON 字符串)
│   ├── 示例：{"messages": [{"role":"user","content":"你好"}, {"role":"assistant","content":"你好！"}], "step": 2, "agent_name": null}
│   ├── 含义：会话最新聊天状态快照。每次 run 结束后更新
│   ├── 来源：RunState.model_dump() 序列化
│   └── 子结构：
│       ├── messages: list[ChatMessage] — 完整对话历史
│       │   ├── role: "user" | "assistant" | "system" | "tool"
│       │   ├── content: str — 消息文本
│       │   ├── tool_calls: list（仅 assistant 可能包含）
│       │   └── tool_call_id: str（仅 tool 角色）
│       ├── step: int — 当前对话轮次计数
│       └── agent_name: str|null — 状态关联的 agent 名
│
├── created_at
│   ├── 类型：datetime
│   ├── 示例："2026-06-12 10:30:00"
│   ├── 默认：server_default=now()，插入时自动生成
│   └── 含义：会话创建时间
│
├── updated_at
│   ├── 类型：datetime
│   ├── 示例："2026-06-12 14:25:00"
│   ├── 默认：等于 created_at，每次 UPDATE 自动刷新（onupdate=now()）
│   └── 含义：会话最后一次更新时间，列表页按此字段倒序排列
│
├── last_agent_name
│   ├── 类型：string，可空，有索引
│   ├── 可选值："software_engineer" | "default" | 自定义 agent 名 | null
│   ├── 示例："software_engineer"
│   └── 含义：最近一次 run 使用的 Agent 名称。每次 run 结束时由 RunPersistenceService 更新，仅供列表页展示
│
├── message_count
│   ├── 类型：integer
│   ├── 示例：15
│   ├── 默认：0
│   └── 含义：当前 state.messages 的总条数，列表页展示
│
├── last_reply_preview
│   ├── 类型：string(120)，可空
│   ├── 示例："好的，我已经帮你创建了三个文件..."
│   ├── 来源：build_reply_preview(partial_reply) 截取前 120 字符
│   └── 含义：最近一次 AI 回复的文字预览，列表页副标题
│
├── permission_profile
│   ├── 类型：string
│   ├── 可选值："conservative" | "moderate" | "permissive"
│   ├── 默认："conservative"
│   └── 含义：安全权限档位，决定工具调用的审批策略
│       ├── "conservative" → 高频审批（高风险工具 + 工作区外写入都要审批）
│       ├── "moderate"    → 中等审批（仅高风险工具审批）
│       └── "permissive"  → 几乎不审批
│       └── 定义位置：security/policy/types.py PROFILES 字典
│
├── context_tokens
│   ├── 类型：integer，可空
│   ├── 示例：4256
│   ├── 来源：每次 run 完成后的 usage.input_tokens（由 RunPersistenceService 更新）
│   └── 含义：最近一次 run 的输入 token 用量，auto-compact 用它判断是否 ≥70% 上下文长度
│
├── model_provider_id
│   ├── 类型：integer (FK → provider_configs.id, ON DELETE SET NULL)，可空
│   ├── 示例：1
│   ├── 默认：创建会话时自动填入默认 Provider
│   └── 含义：会话绑定的 AI 服务商 ID。null 则发起 run 时会报错
│
├── model_id
│   ├── 类型：string，可空
│   ├── 示例："deepseek-chat"
│   ├── 默认：创建会话时自动填入默认模型
│   └── 含义：会话绑定的模型名称，与 model_provider_id 联合查 model_settings 表获取 context_length
│
├── thinking_enabled
│   ├── 类型：integer (0 或 1)
│   ├── 可选值：0 | 1
│   ├── 默认：0
│   └── 含义：是否开启深度思考（reasoning），开启后 ChatCompletionsAdapter 构建时注入 thinking payload
│
├── thinking_effort
│   ├── 类型：string
│   ├── 可选值："low" | "medium" | "high"
│   ├── 默认："medium"
│   └── 含义：深度思考的努力程度，透传给模型 API。仅 thinking_enabled=1 时生效
│
├── workspace_path
│   ├── 类型：string，可空
│   ├── 示例："/Users/wangxu/my-project"
│   └── 含义：会话绑定的本地工作区物理绝对路径。文件类工具基于此 + SandboxMiddleware 做路径解析和 VFS 叠加
│
├── workspace_name
│   ├── 类型：string，可空
│   ├── 示例："my-project"
│   └── 含义：工作区展示名称，纯前端列表页用
│
├── session_type
│   ├── 类型：string
│   ├── 可选值："coding" | "assistant"
│   ├── 默认："coding"
│   └── 含义：会话类型，影响 effective_agent_name 的解析逻辑
│       ├── "coding"    → effective_agent_name 强制为 "software_engineer"
│       └── "assistant" → effective_agent_name = agent_input.agent_name or "default"
│
├── parent_session_id
│   ├── 类型：string (FK → session_records.session_id, ON DELETE SET NULL)，可空
│   ├── 示例：null（普通会话）或 "a1b2c3d4e5f6"（fork 出来的会话）
│   └── 含义：fork 溯源标记。普通创建的会话为 null，从某个会话分叉出来的会话指向父会话
│
└── fork_message_index
    ├── 类型：integer，可空
    ├── 示例：null（普通会话）或 8（在第 8 条消息处截断）
    └── 含义：fork 时在父会话的第几条消息处截断。与 parent_session_id 配对使用
```

---

## 2. `session_runs` — 运行记录表

一行代表一次 Agent 执行（一个 run）。是 session_run_events 和 tool_call_records 的父表。

```
session_runs
│
├── id
│   ├── 类型：integer (PK，自增)
│   └── 含义：内部自增 ID，不对外暴露
│
├── session_id
│   ├── 类型：string (FK → session_records.session_id, ON DELETE CASCADE)，有索引
│   ├── 示例："a3f2b1c8d9e4"
│   └── 含义：这次 run 属于哪个会话。删会话时级联删除所有 run
│
├── parent_run_id
│   ├── 类型：string (FK → session_runs.run_id, ON DELETE SET NULL)，可空，有索引
│   ├── 示例：null（顶层 run）或 "run_abc123"（子 Agent 的父 run）
│   └── 含义：子 Agent 运行的父 run ID。顶层 run 为 null。删父 run 时子 run 的此字段置 null
│
├── run_id
│   ├── 类型：string (UNIQUE)
│   ├── 示例："a7f3e2c1b5d8"
│   ├── 来源：uuid.uuid4().hex
│   └── 含义：本轮运行的全局唯一 ID
│
├── run_status
│   ├── 类型：string
│   ├── 可选值："running" | "completed" | "paused" | "cancelled" | "failed"
│   ├── 默认："running"
│   ├── 来源：RunFinalStatus 枚举映射
│   └── 含义：运行终态
│       ├── "running"    → 执行中（通常不会长期停留此状态）
│       ├── "completed"  → 正常结束，LLM 给出最终文字回复，VFS staged → commit
│       ├── "paused"     → 暂停等待审批，pending_approvals 中有待处理工单
│       ├── "cancelled"  → 用户取消（GeneratorExit / CancelledError），VFS discard
│       └── "failed"     → 异常终止（LLM API 报错、工具崩溃等），VFS discard
│
├── agent_name
│   ├── 类型：string，可空，有索引
│   ├── 示例："software_engineer"
│   ├── 来源：ctx.effective_agent_name
│   └── 含义：本轮实际使用的 Agent 名称。用于 trace 展示和列表筛选
│
├── user_input
│   ├── 类型：text
│   ├── 示例："帮我写一个 Python 脚本"
│   ├── 来源：RunInput.user_input
│   └── 含义：用户本轮输入的原始文本
│
├── reply
│   ├── 类型：text
│   ├── 示例："好的，这是你要的脚本...\n```python\n...\n```"
│   ├── 默认：空字符串
│   └── 含义：AI 最终文字回复，或中断时的 partial_reply
│
├── event_count
│   ├── 类型：integer
│   ├── 示例：7
│   ├── 默认：0
│   └── 含义：本次 run 产生的事件数量（对应 session_run_events 行数），前端展示步骤数
│
├── created_at
│   ├── 类型：datetime
│   ├── 示例："2026-06-12 14:20:00"
│   ├── 默认：server_default=now()
│   └── 含义：run 创建时间
│
├── finished_at
│   ├── 类型：datetime
│   ├── 示例："2026-06-12 14:20:15"
│   ├── 默认：创建时写入，终态时更新
│   └── 含义：run 结束时间
│
└── is_active
    ├── 类型：string
    ├── 可选值："0" | "1"
    ├── 默认："1"（server_default="1"）
    └── 含义：是否活跃。compact 或 reset 时旧的顶层 run 被标记为 "0"，trace 查询据此过滤
```

---

## 3. `session_run_events` — 运行事件表

一行代表 run 内部的一个步骤事件，按 event_index 严格有序。

```
session_run_events
│
├── id
│   ├── 类型：integer (PK，自增)
│   └── 含义：内部自增 ID
│
├── run_id
│   ├── 类型：string (FK → session_runs.run_id, ON DELETE CASCADE)，有索引
│   ├── 示例："a7f3e2c1b5d8"
│   └── 含义：归属哪个 run。删 run 时级联删除所有事件
│
├── event_index
│   ├── 类型：integer
│   ├── 示例：0, 1, 2, 3...
│   └── 含义：事件在本次 run 中的序号，从 0 开始严格递增，前端据此还原执行时间线
│
├── type
│   ├── 类型：string
│   ├── 定义位置：execution/runtime/types.py RunEvent.type (Literal)
│   ├── 可选值及含义：
│   │   ├── "assistant_tool_call"  → AI 决定调用一个工具
│   │   │   ├── 生成点：tool_runner.py handle_tool_calls() / async_handle_tool_calls()
│   │   │   ├── 时机：每轮 LLM 返回 tool_calls 后，在实际执行前
│   │   │   ├── content = tool_call.function.arguments（JSON 字符串）
│   │   │   └── tool_name / tool_call_id 均有值
│   │   │
│   │   ├── "tool_result"  → 工具执行成功
│   │   │   ├── 生成点：tool_runner.py
│   │   │   ├── 时机：工具执行完毕且 ok=True
│   │   │   ├── content = 工具返回的文本内容
│   │   │   ├── tool_result = 完整 ToolResult 对象（含 ok, content, metadata）
│   │   │   └── tool_name / tool_call_id 均有值
│   │   │
│   │   ├── "tool_error"  → 工具执行失败
│   │   │   ├── 生成点：tool_runner.py
│   │   │   ├── 时机：工具执行抛出异常 / 超时 / ok=False
│   │   │   ├── content = "[TOOL_ERROR] {error_message}" 或 "[TOOL_TIMEOUT] ..."
│   │   │   ├── tool_result = 包含 error 信息的 ToolResult
│   │   │   └── tool_name / tool_call_id 均有值
│   │   │
│   │   ├── "final_answer"  → AI 最终文字回复
│   │   │   ├── 生成点：response_handler.py build_final_turn()
│   │   │   ├── 时机：LLM finish_reason 不是 tool_calls，给出最终文本
│   │   │   ├── content = 去首尾空白后的回复全文
│   │   │   └── tool_name / tool_call_id / tool_result 均为 null
│   │   │
│   │   ├── "approval_required"  → 工具调用需要人工审批
│   │   │   ├── 生成点：tool_runner.py async_handle_tool_calls()
│   │   │   ├── 时机：工具批次中有需要审批的项，且审批策略要求人工介入
│   │   │   ├── content = approval_id（审批单号 UUID）
│   │   │   └── tool_name / tool_call_id 均有值
│   │   │
│   │   └── "thinking"  → AI 的推理/思考过程
│   │   │   ├── 生成点：execution_session.py RunExecutionSession.run()
│   │   │   ├── 时机：AgentRunner 产出 thinking_delta 流式片段后，由 execution_session 收集并收束为一个正式事件
│   │   │   ├── content = 完整思考文本
│   │   │   └── tool_name / tool_call_id / tool_result 均为 null
│   │
│   └── 定义代码：
│       type: Literal[
│           "assistant_text",
│           "assistant_tool_call",
│           "tool_result",
│           "tool_error",
│           "final_answer",
│           "approval_required",
│           "thinking",
│       ]
│
├── content
│   ├── 类型：text
│   ├── 示例（按 type）：
│   │   ├── assistant_tool_call: '{"path":"/a.txt","content":"hello"}'
│   │   ├── tool_result: "文件写入成功，共 1024 字节"
│   │   ├── tool_error: "[TOOL_ERROR] Permission denied: /etc/passwd"
│   │   ├── final_answer: "好的，我已经帮你完成了..."
│   │   ├── approval_required: "approval-uuid-xxx"
│   │   └── thinking: "用户想要创建文件，我需要先确认..."
│   └── 含义：事件的主体文本内容，前端直接展示
│
├── tool_name
│   ├── 类型：string，可空
│   ├── 示例："fs_write" | "search_files" | null
│   ├── 默认：null（thinking / final_answer 事件时为 null）
│   └── 含义：工具名称。仅 assistant_tool_call / tool_result / tool_error / approval_required 有值
│
├── tool_call_id
│   ├── 类型：string，可空
│   ├── 示例："call_abc123def456"
│   ├── 默认：null
│   └── 含义：LLM 分配的工具调用 ID，用于配对同一个工具调用的 tool_call → tool_result/tool_error 事件
│
├── tool_result_json
│   ├── 类型：text (JSON 字符串)，可空
│   ├── 示例：{"ok":true,"content":"写入成功","metadata":{"bytes_written":1024,"state":"committed"}}
│   ├── 默认：null（非 tool_result / tool_error 事件时为 null）
│   └── 含义：工具执行的完整结果 JSON，包含：
│       ├── ok: bool — 执行是否成功
│       ├── content: str — 工具返回文本
│       ├── error: {message, code} — 仅失败时有
│       └── metadata: dict — 附加元数据（如 VFS state: "staged"/"committed"/"rolled_back"）
│
└── created_at
    ├── 类型：datetime
    ├── 示例："2026-06-12 14:20:03"
    ├── 默认：server_default=now()
    └── 含义：事件记录时间
```
