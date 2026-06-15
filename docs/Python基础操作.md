## 0. LLM API 协议格式



request Hearder:

~~~json
{
  "model":"my_model_name",
  "message":[
    {
      "role":"system",
      "content":"",
    },
    {
      "role":"user",
      "content":""
    },
    {
      "role":"assistant",
      "content":null,
      "tool_calls":[
        {
          "id":"tool_call_id_001",
          "type":"function",
          "function":{
            "name":"get_weather",
            "arguments":{city:"beijing"}
          }
        }
      ]
    },
    {
      "role":"tool",
      "tool_call_id":"tool_call_id_001",
      "content":"今天天气晴朗",
    }
  ],
  "stream":true,
  "tools":[
    {
      "type":"function",
      "function":{
        "name":"get_weathaer",
        "description":"用来查询用户指定的天气",
        "parameters":{
          "type":"object",
          "properties":{
            "city":{
              "type":"string",
              "description":"用户要查询的天气名称",
            },
            "data":{
              "type":"string",
              "description":"用户要查询的具体日期",
            },
          },
          "required":{"city","data"},
        }
      }
    }
  ],
  "tool_chocies":auto,
}
~~~

~~~markdown
一次大模型请求 Request
│
├── model
│   ├── 类型：string
│   ├── 示例："your-model-name"
│   └── 含义：指定本次调用使用哪个模型
│
├── messages
│   ├── 类型：list
│   ├── 含义：发送给模型的完整对话上下文
│   │
│   ├── [0] system 消息
│   │   ├── role = "system"
│   │   ├── content = 系统提示词
│   │   └── 含义：规定模型身份、行为规则、工具使用原则
│   │
│   ├── [1] user 消息
│   │   ├── role = "user"
│   │   ├── content = 用户的问题
│   │   └── 含义：用户本轮输入
│   │
│   ├── [2] assistant 消息（模型要求调用工具时）
│   │   ├── role = "assistant"
│   │   ├── content = null 或少量文本
│   │   ├── tool_calls
│   │   │   ├── 类型：list
│   │   │   └── 含义：模型生成的一个或多个工具调用计划
│   │   │
│   │   │   └── [0] 一个工具调用
│   │   │       ├── id
│   │   │       │   ├── 示例："call_001"
│   │   │       │   └── 含义：这一次工具调用的唯一标识
│   │   │       │
│   │   │       ├── type = "function"
│   │   │       │   └── 含义：调用的是函数型工具
│   │   │       │
│   │   │       └── function
│   │   │           ├── name
│   │   │           │   └── 含义：要调用的工具名称
│   │   │           │
│   │   │           └── arguments
│   │   │               ├── 类型：JSON 字符串
│   │   │               ├── 示例："{\"city\":\"北京\"}"
│   │   │               └── 含义：模型为工具生成的实际参数
│   │   │
│   │   └── 含义：这不是最终回答，而是模型要求 Runtime 执行工具
│   │
│   └── [3] tool 消息（Runtime 执行工具后追加）
│       ├── role = "tool"
│       ├── tool_call_id = "call_001"
│       │   └── 含义：关联上一条 assistant.tool_calls 中的 id
│       ├── content
│       │   ├── 类型：通常是字符串
│       │   ├── 示例："{\"weather\":\"晴\",\"temperature\":28}"
│       │   └── 含义：工具真实执行后返回的结果
│       └── 含义：把工具结果交回模型继续生成
│
├── tools
│   ├── 类型：list
│   ├── 含义：本次请求允许模型使用的工具说明
│   │
│   └── [0] 一个工具定义
│       │
│       ├── type = "function"
│       │   └── 含义：这是函数型工具
│       │
│       └── function
│           │
│           ├── name
│           │   ├── 示例："get_weather"
│           │   └── 含义：工具名称
│           │
│           ├── description
│           │   └── 含义：说明工具做什么，帮助模型判断是否调用
│           │
│           └── parameters
│               ├── 含义：工具参数的 JSON Schema
│               │
│               ├── type = "object"
│               │   └── 含义：所有参数组成一个 JSON 对象
│               │
│               ├── properties
│               │   ├── 含义：定义允许传入的每一个参数
│               │   │
│               │   └── city
│               │       ├── type = "string"
│               │       │   └── 含义：city 必须是字符串
│               │       ├── description
│               │       │   └── 含义：解释 city 参数用途
│               │       ├── minLength
│               │       │   └── 含义：字符串最短长度
│               │       └── maxLength
│               │           └── 含义：字符串最长长度
│               │
│               ├── required
│               │   ├── 示例：["city"]
│               │   └── 含义：列出必须提供的参数
│               │
│               └── additionalProperties = false
│                   └── 含义：禁止生成 properties 中未定义的额外参数
│
├── tool_choice
│   ├── 示例："auto"
│   └── 含义：控制模型如何选择工具
│              auto：模型自行判断
│              none：禁止调用工具
│              指定工具：强制调用某个工具
│
├── temperature
│   ├── 示例：0.2
│   └── 含义：控制输出随机性
│
├── stream
│   ├── 示例：true
│   └── 含义：是否使用流式响应
│
└── stream_options
    └── include_usage = true
        └── 含义：在流结束前额外返回 token 使用量
~~~

## 1. RunContext — 拼接一次 run 的上下文

~~~树形
run_input: RunInput
├── session_id: str
│   ├── 示例："session-abc123"
│   └── 含义：本轮 run 归属的 session，所有后续查询都基于它
├── user_input: str
│   ├── 示例："帮我查一下项目结构"
│   └── 含义：用户本轮输入的原始文本
├── agent_name: Optional[str]
│   ├── 示例："code-reviewer"
│   └── 含义：显式指定本轮使用的 agent（不传则自动推断）
└── skill_name: Optional[str]
    ├── 示例："find-skills"
    └── 含义：显式加载某个 skill 的完整内容到 system prompt

────────────────────────────────────────────────────

RunContextFactory.assemble(run_input) 的组装过程：

├── 1. _load_record(session_id)
│   └── 查 SessionRecord 表，拿到以下 session 级配置：
│       ├── model_provider_id  → 模型供应商 ID
│       ├── model_id           → 模型名称
│       ├── workspace_path     → 工作区物理路径
│       ├── session_type       → "coding" | "assistant"
│       ├── permission_profile → "conservative" | "moderate" | "permissive"
│       ├── context_tokens     → 上次调用的 input tokens（压缩预算参考）
│       └── thinking_enabled   → 是否开启深度思考
│
├── 2. _create_adapter(session_id, record) → ChatCompletionsAdapter
│   ├── 查 ProviderConfig 表 → api_key, base_url
│   ├── 查 ModelSetting 表  → context_length
│   └── build_thinking_payload(model_setting) → extra_payload
│       ├── 示例：{"thinking": {"type": "enabled", "effort": "medium"}}
│       └── 含义：思考模式的 provider 特定参数，合并进每轮 LLM 请求
│
├── 3. state = SessionStore.get(session_id) or RunState()
│   ├── 拿到最新的对话状态快照：
│   │   ├── messages: list[ChatMessage]  → 历史对话记录
│   │   └── step: int                     → 当前步数计数
│   │
│   └── 自动压缩（如果 messages 非空）：
│       ├── HistoryCompactor(adapter)                → 用 adapter 生成摘要
│       └── CompactService.auto_compact_in_memory()  → 按 context_length 预算裁剪
│           ├── context_tokens      → 上次消耗的 token 数（判断触发阈值）
│           ├── context_length      → 模型最大上下文长度
│           └── keep_recent_count=2 → 保留最近 2 轮对话
│
├── 4. effective_agent_name = _resolve_effective_agent_name(run_input, session_type)
│   ├── session_type == "coding" → "software_engineer"
│   │   └── 含义：coding 模式默认用软件工程师 agent
│   └── 否则 → run_input.agent_name or "default"
│       └── 含义：assistant 模式可用前端指定的 agent，不传则用 default
│
├── 5. AgentDefinitionService.load_definition(effective_agent_name)
│   └── 从 agent 定义表加载 AgentDefinition：
│       ├── system_prompt   → 基础系统提示词
│       ├── tool_names      → 允许使用的工具白名单
│       └── description     → agent 描述
│
├── 6. ContextAssembler.assemble(…) → 合并运行时系统提示词
│   ├── _load_workspace_context(workspace_path, session_type)
│   │   ├── 工作区根目录 / AGENTS.md    → local_rules_text（项目级指令）
│   │   └── 仅 assistant 模式：
│   │       ├── 工作区根目录 / SOUL.md  → agent_soul_text（人设描述）
│   │       └── 工作区根目录 / USER.md  → user_profile_text（用户画像）
│   │
│   └── SkillContextService.build_runtime_definition_with_skills()
│       ├── build_skill_catalog_prompt()
│       │   └── 含义：始终往 system prompt 末尾追加所有可用 skill 的概要列表
│       └── 如果 run_input.skill_name 非空：
│           ├── load_skill_content(skill_name)  → 加载该 skill 的完整内容
│           └── 含义：把 skill 的详细指令注入 system prompt
│       → 返回合并后的 system_prompt 文本
│
├── 7. runtime_definition = definition.model_copy(update={"system_prompt": new_prompt})
│   └── 含义：复制基础 AgentDefinition，只替换 system_prompt 为合并后的版本
│       ├── tool_names 保持不变（来自 definition 的白名单）
│       └── 上游通过 agent_profile.tool_names 读取
│
├── 8. approval_policy = _resolve_approval_policy(record)
│   └── permission_profile → PROFILES 查表 → ApprovalPolicy
│       ├── conservative → ApprovalPolicy.ALWAYS
│       ├── moderate     → ApprovalPolicy.HIGH_RISK_ONLY
│       └── permissive   → ApprovalPolicy.NEVER
│
└── 9. 最终返回 RunContext
    ├── state: RunState
    │   ├── 示例：messages=[ChatMessage(role="system", content="你是一个助手"), ...], step=3
    │   └── 含义：本轮启动时的对话状态快照（已压缩）
    ├── agent_profile: AgentDefinition
    │   ├── 示例：system_prompt="你是软件工程师...\n可用技能：...", tool_names=["read_file","write_file"]
    │   └── 含义：最终生效的 agent 定义（system prompt + 工具白名单）
    ├── adapter: ChatCompletionsAdapter
    │   ├── 示例：ChatCompletionsAdapter(base_url="https://api.example.com", model="gpt-4")
    │   └── 含义：已绑定 session 模型配置的通讯器，下游直接调 adapter.generate()
    ├── approval_policy: ApprovalPolicy
    │   ├── 示例：ApprovalPolicy.HIGH_RISK_ONLY
    │   └── 含义：工具审批策略，传到 tool_runner 控制审批行为
    ├── effective_agent_name: str
    │   ├── 示例："software_engineer"
    │   └── 含义：本轮实际使用的 agent 名称（落库 + 前端显示用）
    ├── workspace_path: str
    │   ├── 示例："/Users/wangxu/projects/my-app"
    │   └── 含义：物理工作区路径（文件工具 + VFS 的根目录）
    └── session_type: str
        ├── 示例："coding"
        └── 含义：会话类型（决定 agent 选择 + prompt 组装 + 沙箱策略）
~~~

────────────────────────────────────────────────────

## 2. ToolTracer — 工具执行观察者

~~~树形
ToolTracer(db, run_store, approval_store, session_id, run_id, run_input)

构造参数：
├── db: Session
│   └── 含义：统一数据库会话，每次回调内部 commit
├── run_store: RunTraceStore
│   └── 含义：run trace 持久化存储，提供以下方法：
│       ├── create_tool_call(run_id, tool_name, tool_call_id, input_json) → record_id
│       │   └── 含义：工具开始执行时创建 "running" 状态记录
│       ├── finish_tool_call(record_id, status, result_json)
│       │   └── 含义：工具结束时更新状态为 "completed" | "failed" | "timeout"
│       ├── save_run_trace(session_id, run_id, agent_name, user_input, reply, events)
│       │   └── 含义：保存完整 run 记录 + 所有事件到 SessionRunEventRecord 表
│       └── save_partial_run(...)
│           └── 含义：保存未完成的 run 记录（中断/审批暂停场景）
├── approval_store: SqliteApprovalStore
│   └── 含义：审批记录持久化存储
├── session_id: str
│   └── 含义：所属会话 ID
├── run_id: str
│   └── 含义：本轮 run 的唯一 ID
└── run_input: RunInput
    └── 含义：本轮用户输入，透传备用

三个回调方法（挂载到 async_handle_tool_calls）：

├── on_tool_start(tool_name, tool_call_id, input_json) → record_id
│   ├── 触发时机：每个工具开始执行前
│   └── 副作用：run_store.create_tool_call() + db.commit()
│
├── on_tool_finish(record_id, status, result_json)
│   ├── 触发时机：每个工具执行结束后
│   ├── status 取值："completed" | "failed" | "timeout"
│   └── 副作用：run_store.finish_tool_call() + db.commit()
│
└── on_approval_required(tool_call_id, tool_name, arguments, saved_messages, event_index, batch_id) → approval_id
    ├── 触发时机：工具需要人工审批时
    └── 副作用：approval_store.create() + db.commit()
~~~

────────────────────────────────────────────────────

## 3. AgentRunner — 智能体发动机构造

~~~树形
AgentRunner(
    state=ctx.state,
    agent_profile=ctx.agent_profile,
    model_adapter=ctx.adapter,
    tool_registry=build_run_registry(child_dispatcher, status_checker, child_waiter),
    approval_policy=ctx.approval_policy,
    session_type=ctx.session_type,
)

构造参数：
├── state: RunState
│   └── 含义：当前对话状态快照（messages + step），来自 ctx.state（已压缩）
├── agent_profile: AgentDefinition
│   └── 含义：最终生效的 agent 定义，包含合并后的 system_prompt + tool_names
├── model_adapter: ChatCompletionsAdapter
│   └── 含义：大模型通讯器，AgentRunner 直接调 adapter.async_stream_generate()
├── tool_registry: ToolRegistry
│   └── build_run_registry() 构建，注入三个闭包回调：
│       ├── child_dispatcher: ChildRunLauncher.create_launcher(run_id, session_id)
│       │   └── 含义：子 Agent 启动回调（供 agent_bridge 工具使用）
│       ├── status_checker: ChildRunLauncher.create_status_checker()
│       │   └── 含义：子 Agent 状态查询回调
│       └── child_waiter: ChildRunLauncher.create_waiter()
│           └── 含义：子 Agent 等待完成回调
├── approval_policy: ApprovalPolicy
│   └── 含义：工具审批策略，传到 async_handle_tool_calls 控制审批逻辑
└── session_type: str
    └── 含义：会话类型，传到 async_handle_tool_calls 决定安全中间件管道
        ├── "coding" → MiddlewarePipeline([SandboxMiddleware()])  → 启用沙箱
        └── 其他     → MiddlewarePipeline([])                       → 空管道
~~~
────────────────────────────────────────────────────

## 4. RunSSEBridge — SSE 协议适配

~~~树形
RunSSEBridge(
    ctx, observer, agent_runner, run_id, run_input, recorder
)

构造参数：
├── ctx: RunContext
│   └── 含义：第 1 步组装的完整运行背景（effective_agent_name 用于 start 帧）
├── observer: ToolTracer
│   └── 含义：第 2 步构建的工具追踪器，三个回调传给 RunLifecycle
├── agent_runner: AgentRunner
│   └── 含义：第 3 步构建的执行发动机
├── run_id: str
│   └── 含义：本轮 run 的唯一 ID（start 帧 / paused 帧用到）
├── run_input: RunInput
│   └── 含义：用户输入（session_id + agent_name 用于 start 帧）
└── recorder: RunRecorder
    └── 含义：终态持久化入口

────────────────────────────────────────────────────

stream() 方法执行流程：

yield start 帧
│   ├── session_id, run_id, agent_name
│   └── 含义：告诉前端"一轮新 run 开始了"，准备接收后续帧
│
├── 构建 RunLifecycle(params)
│   ├── ctx            → ctx 完整传入
│   ├── agent_runner   → 发动机
│   ├── recorder       → 持久化
│   ├── run_input      → 用户输入
│   ├── run_id         → run ID
│   ├── on_tool_start     ← observer.on_tool_start
│   ├── on_tool_finish    ← observer.on_tool_finish
│   ├── on_approval_required ← observer.on_approval_required
│   ├── skip_user_message  → 默认 False（resume 时为 True）
│   ├── event_index        → 默认 0（resume 时从上次断点接着编号）
│   ├── initial_events     → 默认空（resume 时补 tool_result 事件）
│   ├── is_resume          → 默认 False（resume 时为 True，往已有 run 追加事件）
│   └── owns_session       → 默认 True（子 Agent 设为 False，防止污染主 session）
│
└── async for item in lifecycle.iterate():
    │
    ├── TextDeltaItem  → SSE "delta" 帧
    │   ├── type="delta"
    │   └── data={content: "文本片段"}
    │
    ├── ThinkingDeltaItem → SSE "thinking_delta" 帧
    │   ├── type="thinking_delta"
    │   └── data={content: "思考片段"}
    │
    ├── RunEventItem → SSE "run_event" 帧
    │   └── data=event.model_dump()
    │       ├── index, type, content, tool_name, tool_call_id
    │       └── 可能的 type：assistant_tool_call / tool_result / tool_error / thinking / final_answer / approval_required
    │
    └── RunStatusItem → 终态帧
        ├── status == PAUSED → SSE "paused" 帧
        │   └── data={run_id}  → 前端跳转审批界面
        └── status 其他 → SSE "end" 帧
            └── data={state: agent_runner.state.model_dump()}
                ├── messages + step
                └── 含义：前端展示最终状态摘要
~~~

────────────────────────────────────────────────────

## 5. RunLifecycle.iterate() — 执行生命周期

~~~树形
iterate() 内部准备

├── reply_text = ""         → 累积最终回复文本
├── thinking_buf = ""       → 累积思考文本片段
├── events: list[RunEvent]  → 正式事件账本
│   └── 初始值 = initial_events（resume 场景预先填入，默认空）
│
└── _flush_thinking() 内联异步生成器
    └── 作用：把 thinking_buf 收束成一条 RunEvent(type="thinking")
        ├── 创建 RunEvent(index=len(events), type="thinking", content=thinking_buf)
        ├── events.append(event)
        ├── thinking_buf 清空
        └── yield RunEventItem(event=event)

────────────────────────────────────────────────────

主循环：async for item in agent_runner.async_stream_run(...)

传入参数：
├── run_input           → 用户输入
├── on_tool_start       → ToolTracer.on_tool_start
├── on_tool_finish      → ToolTracer.on_tool_finish
├── on_approval_required → ToolTracer.on_approval_required
├── skip_user_message   → 是否跳过自动追加 user message
├── event_index         → 事件序号起点
├── run_id              → run ID
└── workspace_path      → 工作区物理路径

对每个产出的 item 分类处理：

├── isinstance(item, str)
│   ├── reply_text += item                          → 累积到最终回复
│   └── yield TextDeltaItem(content=item)           → 实时透传文字片段
│
├── isinstance(item, StreamChunk) and type == "thinking_delta"
│   ├── thinking_buf += item.thinking_delta         → 攒着，不收束
│   └── yield ThinkingDeltaItem(content=chunk)      → 实时透传思考片段
│
└── isinstance(item, RunEvent)
    ├── type in ("tool_result", "tool_error")
    │   └── reply_text = ""                       → 工具结果之后最终回复重新累计
    │
    ├── _flush_thinking()                         → 先把积攒的 thinking 收束成事件
    ├── events.append(item)                       → 记入正式事件账本
    └── yield RunEventItem(event=item)            → 透传

────────────────────────────────────────────────────

循环结束后的终态收口

正常结束（循环自然退出）：
├── _flush_thinking()                              → 最后一次收束 thinking
├── 判断终态：
│   ├── events 中有 approval_required → PAUSED
│   └── 否则                          → COMPLETED
├── _build_finalization(status, events, reply)  → 组装 RunFinalizationInput（reply 来自局部变量 reply_text）
│   ├── 入参：status / events / reply 三个循环产物
│   └── 自取：run_id, session_id, user_input, state, agent_name, usage, is_resume, owns_session
├── recorder.finalize_run(finalization)            → 终态落库
│   ├── 写 SessionRunRecord（run 摘要）
│   ├── 写 SessionRunEventRecord（每条 event 一行）
│   ├── 更新 SessionRecord.state_json（最新对话状态）
│   ├── completed → VFS.commit_all()     → staged 文件落盘
│   └── 更新 run_status = "completed"
└── yield RunStatusItem(status=status)             → RunSSEBridge 据此发 end / paused 帧

被取消（GeneratorExit / asyncio.CancelledError）：
├── _flush_thinking()
├── recorder.finalize_run(_build_finalization(status=CANCELLED, ...))
│   ├── CANCELLED / FAILED → VFS.discard() → staged 文件删除
│   └── 写部分事件到 DB
└── raise                                          → 往上抛，让 Starlette 处理清理

异常（Exception）：
├── _flush_thinking()
├── recorder.finalize_run(_build_finalization(status=FAILED, ...))
│   └── VFS.discard()
└── raise                                          → 往上抛
~~~

────────────────────────────────────────────────────

## 6. AgentRunner.async_stream_run() — 引擎内部

~~~树形
循环前的准备：

0. 追加 user message（带去重）
   ├── skip_user_message=True → 跳过（resume 场景）
   ├── skip_user_message=False → 倒序查找最后一条 user 消息
   │   ├── 找到了且 content 相同 → 跳过（retry / 中断续跑，避免重复）
   │   └── 找不到或 content 不同 → state.messages.append(user)
   └── 目的：防止中断后 save_partial_run 补 assistant + retry 新 run 时 user message 重复

while True 循环体（一次迭代 = 一轮 LLM 对话）：

1. 组装请求
   request = build_model_request(agent_profile, state, tool_registry)
   └── system_prompt + state.messages + tools

2. 消费 LLM 流（逐帧处理 StreamChunk）
   async for chunk in adapter.async_stream_generate(request):
   │
   ├── type="done" + usage
   │   └── self.last_usage = chunk.usage      → 只记录，不 yield
   │
   ├── type="thinking_delta"
   │   └── yield chunk                         → 原样透传给 RunLifecycle
   │
   ├── type="content_delta"
   │   ├── yield chunk.content_delta           → 拆成裸字符串 yield
   │   └── raw_reply_chunks.append(...)        → 攒着，备用
   │
   └── type="tool_call_delta"
       └── 按 index 分组收进 tool_call_buffers
           ├── buf["id"]           ← tc.id
           ├── buf["name_chunks"]  ← function.name 片段
           └── buf["args_chunks"]  ← function.arguments 片段

3. 判定 finish_reason（LLM 流结束后）
   ├── finish_reason == "tool_calls"
   │   ├── 拼接 ToolCall 列表
   │   │   ├── id = buf["id"]
   │   │   ├── function.name = "".join(buf["name_chunks"])
   │   │   └── function.arguments = "".join(buf["args_chunks"])
   │   │       └── 注意：name 和 args 可能跨多帧，靠 index 归组
   │   │
   │   ├── 构造 assistant ChatMessage
   │   │   ├── content = raw_reply_chunks 拼接（可能为 None）
   │   │   │   └── 含义：模型可能在 tool_calls 前先说一段话（content lead-in）
   │   │   └── tool_calls = 拼接好的列表
   │   │
   │   ├── 执行工具 async_handle_tool_calls(...)
   │   │   ├── yield RunEvent → 实时透传工具事件
   │   │   ├── paused_for_approval → break（审批中断）
   │   │   └── 否则 → 更新 event_index → continue 下一轮
   │   │
   │   └── 工具结果追入 state.messages → continue
   │
   └── 其他（stop / length / None）
       ├── build_reply(raw_reply, event_index)
       │   ├── reply = raw_reply.strip()
       │   ├── final_event = RunEvent(type="final_answer")
       │   └── assistant_message = ChatMessage(role="assistant")
       │
       └── yield final_event → break

关键细节：

├── raw_reply_chunks 和 tool_call_buffers 每轮重置
│   └── 含义：每轮 LLM 调用独立，不跨轮累积
│
├── finish_reason 只取最后一个非 None 值
│   └── 含义：流中间帧 finish_reason 为 None，最后一帧才有值
│
├── content lead-in bug 修复
│   └── 模型吐了 content 再吐 tool_calls → raw_reply_chunks 非空
│       → assistant message 同时保留了 content 和 tool_calls
│
└── yield 出去的三种形态
    ├── str                → 正文片段（RunLifecycle 攒起来）
    ├── StreamChunk        → thinking_delta 片段（RunLifecycle 攒起来）
    └── RunEvent           → 正式事件（RunLifecycle 透传或收束 thinking 后再传）
~~~



────────────────────────────────────────────────────

## 7. ChatCompletionsAdapter — 大模型通讯

~~~树形
一、初始化阶段（RunContextFactory 构建，整个 run 复用）

ChatCompletionsAdapter(
    api_key, base_url, model, extra_payload, thinking_style,
)
├── base_url        → 查 SessionRecord.model_provider_id → ProviderConfig.base_url
├── api_key         → 查 ProviderConfig.api_key
├── model           → SessionRecord.model_id（用户选的模型名）
├── extra_payload   → build_thinking_payload(thinking_style, enabled, effort)
│   ├── deepseek_style: {"thinking": {"type": "enabled"}, "reasoning_effort": "medium"}
│   ├── sensenova_style: {"reasoning_effort": "medium"}
│   └── none: {}
└── thinking_style  → 查 ModelSetting.thinking_style

────────────────────────────────────────────────────

二、构造 HTTP 请求

每次 async_stream_generate(request: ModelRequest) 被调用时：

headers:
├── Accept: "text/event-stream"             → 告诉服务器返回 SSE 流
├── Authorization: "Bearer {api_key}"       → 身份认证
└── Content-Type: "application/json"        → 请求体格式

payload:
├── model: request.config.model or self.model
├── messages: [system_prompt, *state.messages]
├── stream: True                              → 强制流式
├── tools: request.tools                      → 工具 JSON Schema 列表
├── tool_choice: "auto"
├── temperature / top_p / max_output_tokens   → 可选参数
├── stream_options: {"include_usage": True}   → 要求返回 token 用量
├── provider_options                          → 合并 request.config.provider_options
└── extra_payload                             → 合并 thinking payload

────────────────────────────────────────────────────

三、建立连接（带重试）

max_retries = 3, delay = 1s → 2s → 4s（指数退避）

async with httpx.AsyncClient(timeout=2100) as client:
    ctx → httpx Stream 上下文管理器（控制连接开关）
    response → 响应头对象（提供 aiter_lines() 逐行读 body）

    尝试 4 次：
        ctx = client.stream("POST", url, headers=headers, json=payload)  → 发请求
        response = await ctx.__aenter__()                                 → 等握手
        response.raise_for_status()                                       → 检查 200
        成功 → break
        失败 → await ctx.__aexit__() 清理 + await asyncio.sleep(delay) 重试

────────────────────────────────────────────────────

四、逐行解析 SSE

async for line in response.aiter_lines():
├── 空行 / 非 "data:" 开头 → 跳过
├── text == "[DONE]"       → break
├── JSON 解析 chunk
│
├── choices 为空（usage 帧）
│   └── yield StreamChunk(type="done", usage=ModelUsage(...))
│
└── choices 非空（内容帧）
    ├── choice = choices[0]
    ├── delta = choice["delta"]
    ├── finish_reason = choice["finish_reason"]
    └── _parse_delta(delta, finish_reason) → 0~N 个 StreamChunk

────────────────────────────────────────────────────

五、_parse_delta — 原始 delta → StreamChunk 打标签

delta 字段         → StreamChunk 产出
────────────────────────────────────────────
reasoning_content  → type="thinking_delta", thinking_delta=值
或 thinking_content
或 reasoning

content            → type="content_delta", content_delta=值,
                      finish_reason=null/"stop"/"tool_calls"

tool_calls         → type="tool_call_delta",
                      tool_call_delta=整个原始delta,
                      finish_reason=null/"stop"/"tool_calls"

为空                → type="done", finish_reason="stop"/"tool_calls"
                      （兜底：最后一帧 delta 为空时）

注意：一个 delta 可以同时有 content + tool_calls → 产出两个 StreamChunk

────────────────────────────────────────────────────

六、原始 choices → StreamChunk 对照表

原始 choices（模型返回的每一帧）：
choices[0]:
    delta:
        content: "你好"                       → content_delta
        reasoning_content: "让我先想一想..."    → thinking_delta
        tool_calls: [{index, id, function}]    → tool_call_delta
    finish_reason: null / "stop" / "tool_calls"

StreamChunk 5 种产出：

type="content_delta"
    content_delta: "你好"
    finish_reason: null（中间帧）或 "stop"/"tool_calls"（最后一帧）

type="thinking_delta"
    thinking_delta: "让我先想一想..."

type="tool_call_delta"
    tool_call_delta: {"tool_calls": [...]}   ← 存整个原始 delta
    finish_reason: null 或 "tool_calls"

type="done"
    finish_reason: "stop" 或 "tool_calls"    ← 空 delta 兜底

type="done"
    usage: {input_tokens, output_tokens, total_tokens}  ← usage 帧
~~~

## 8. RunRecorder — 终态持久化

~~~树形
_finalize_completed（正常完成）：
│
├── ① 标记 VFS 状态：staged → committed
│   └── 遍历所有 events，把 tool_result.metadata["state"] 改为 "committed"
│
├── ② 按 is_resume 分支：
│   │
│   ├── is_resume=True
│   │   ├── owns_session=True → save_state()
│   │   │   ├── 更新 session_records.state_json
│   │   │   ├── last_agent_name
│   │   │   └── last_reply_preview（截断前 120 字）
│   │   │
│   │   └── append_run_events(run_id, events, final_reply)
│   │       ├── 更新 session_runs.reply = final_reply
│   │       └── 追加 N 条 session_run_events（从上次最大 event_index+1 开始）
│   │
│   └── is_resume=False
│       │
│       ├── owns_session=True → save_state()
│       │   ├── 更新 session_records.state_json（最新 messages）
│       │   ├── last_agent_name → agent_name
│       │   ├── last_reply_preview → reply 前 120 字
│       │   └── context_tokens → usage.input_tokens（token 预算参考）
│       │
│       └── save_run_trace(session_id, run_id, agent_name, user_input, reply, events)
│           ├── 写入 session_runs 表（1 条 run 摘要）
│           │   ├── session_id / run_id / agent_name
│           │   ├── user_input / reply
│           │   ├── event_count = len(events)
│           │   └── finished_at = now()
│           │
│           └── 批量写入 session_run_events 表（N 条 event）
│               ├── 每条 event 序列化为：
│               │   ├── run_id / event_index
│               │   ├── type（assistant_text / tool_result / ...）
│               │   ├── content（文本内容）
│               │   ├── tool_name / tool_call_id（工具类 event 才有）
│               │   └── tool_result_json（JSON 序列化的 ToolResult）
│               └── 按 event_index 顺序写入，前端回放时保证时序
│
└── ③ update_run_status(run_id, "completed")
    └── 更新 session_runs.run_status = "completed"

────────────────────────────────────────────────────

_finalize_paused（等待审批）：
│
├── ① 按 is_resume 分支：
│   │
│   ├── is_resume=True
│   │   ├── owns_session=True → save_state(state)
│   │   │   └── 更新 session_records.state_json
│   │   │
│   │   └── append_run_events_partial(run_id, events)
│   │       ├── 只追加 events，不更新 reply
│   │       └── event_count += len(events)
│   │
│   └── is_resume=False
│       │
│       ├── refresh_pending_saved_messages_for_batch(...)
│       │   ├── 查同一 batch 下所有 pending 审批单
│       │   ├── 把 saved_messages 刷新为最新的 state.messages
│       │   └── 用途：恢复执行时能拿到最新对话上下文
│       │
│       └── save_partial_run(session_id, run_id, agent_name, user_input, reply, state, events)
│           ├── 写入 session_runs 表（1 条 run 摘要，reply 不完整）
│           ├── 写入 session_run_events 表（N 条 event）
│           ├── 如果 reply 非空，注入一条 assistant message 到 state.messages
│           └── 把 state 序列化写入 session_records.state_json
│
└── ② update_run_status(run_id, "paused")

────────────────────────────────────────────────────

_finalize_interrupted（取消 / 异常，CANCELLED 和 FAILED 共享）：
│
├── ① _ensure_user_message(state, user_input)
│   ├── 如果 state.messages 为空或最后一条不是 user → 补上 ChatMessage(role="user")
│   └── 含义：取消/异常可能在 user message 添加前就发生，兜底补上
│
├── ② 标记 VFS 状态：staged → rolled_back
│   └── 遍历所有 events，把 tool_result.metadata["state"] 改为 "rolled_back"
│
├── ③ 按 is_resume 分支（同 _finalize_paused）
│   ├── is_resume=True  → save_state + append_run_events_partial
│   └── is_resume=False → save_partial_run（注入 assistant message + 写 snapshot）
│
└── ④ update_run_status(run_id, status.value)
    └── "cancelled" 或 "failed"

────────────────────────────────────────────────────

三个终态方法结束后，finalize_run 统一收口：
│
├── db.commit()
│   └── 上面所有的 .add() / .flush() 在这一刻一次性提交到 SQLite
│
└── _apply_vfs_terminal_action()
    ├── COMPLETED              → VFS.commit_all()
    │   ├── 把 staged 区的文件真正写入物理磁盘
    │   └── RunVfsRegistry.take(run_id)  → 释放 VFS 实例
    │
    └── CANCELLED / FAILED     → VFS.discard()
        ├── staged 文件直接丢弃，不落盘
        └── 含义：取消/失败不产生任何副作用
~~~
## 9. ToolRegistry — 工具注册与执行

~~~树形
ToolRegistry 数据结构：

self._tools: dict[str, ToolDefinition]
├── key = 工具名（"read_file", "write_file", "echo_tool" ...）
└── value = ToolDefinition
    ├── name: str           → 工具名
    ├── description: str    → 给模型看的描述
    ├── schema: dict        → JSON Schema（模型看到的参数契约）
    ├── handler: callable   → 实际执行的 Python 函数
    └── risk_level: enum    → SAFE / SENSITIVE / DANGEROUS

核心方法：

clone()
├── new._tools = dict(self._tools)  ← 浅拷贝字典
├── 用途：每次 run 构建独立副本，避免并发 run 间工具定义互相污染
└── 调用点：build_run_registry() → registry.clone()

get_tool_schemas(tool_names) → list[dict]
├── 传入 tool_names=None → 返回全部工具的 schema
├── 传入 tool_names=["echo_tool"] → 只返回指定工具的 schema
└── 下游：build_model_request() 把 schemas 塞进 LLM 请求的 "tools" 字段

get_risk_level(name) → RiskLevel
├── 查 tool._tools[name].risk_level
└── 下游：approval_checker 判断是否需要审批

execute_tool_call(name, arguments, context) → ToolResult
│
├── ① 沙箱路径校验
│   └── SandboxPathResolver.resolve_and_rewrite(name, arguments, workspace_path)
│       ├── OK → 用改写后的 arguments 继续
│       └── 违规 → 直接返回 ToolResult(ok=False, code="SANDBOX_VIOLATION")
│
├── ② 查工具是否存在
│   └── 不存在 → ToolResult(ok=False, code="unknown_tool")
│
├── ③ JSON 解析 arguments
│   └── 解析失败 → ToolResult(ok=False, code="invalid_arguments")
│
├── ④ 反射检查 handler 签名
│   ├── 如果 handler 定义了 __context__ 参数 → 把 context 注入 args
│   └── 用途：工具可以拿到 workspace_path、VFS 等上下文
│
├── ⑤ 调用 handler(**args)
│   ├── TypeError → ToolResult(ok=False, code="invalid_arguments")
│   └── Exception → ToolResult(ok=False, code="tool_runtime_error")
│
└── ⑥ 包装返回值
    ├── handler 返回 ToolResult → 直接返回
    └── handler 返回其他 → 包装为 ToolResult(ok=True, content=str(result))

三层 try/except（JSON 解析 → TypeError → Exception）保证 Agent 循环永不崩溃

构建链路：

build_default_tool_registry()
├── 注册 6 个内置工具：read_file, write_file, list_dir, search_text, web_search, echo_tool
└── 存入 DEFAULT_TOOL_REGISTRY（模块级单例）

build_run_registry(child_dispatcher, status_checker, child_waiter)
├── DEFAULT_TOOL_REGISTRY.clone()              ← 浅拷贝全局注册表
├── 注册 spawn_child_agent(child_dispatcher)   ← 子 Agent 启动回调
├── 注册 check_child_status(status_checker)    ← 子 Agent 状态查询回调
└── 注册 wait_child_agent(child_waiter)        ← 子 Agent 等待完成回调
    └── 三个子 Agent 桥接工具通过闭包注入回调，工具本身不依赖全局状态

────────────────────────────────────────────────────

具体例子 — 注册并执行一个工具：

① 注册
    registry = ToolRegistry()
    registry.register(ToolDefinition(
        name="echo_tool",
        description="回显用户输入的内容",
        schema={"type": "object", "properties": {"text": {"type": "string"}}},
        handler=my_handler,       ← Python 函数
        risk_level=RiskLevel.SAFE,
    ))
    # 此时 self._tools = {"echo_tool": ToolDefinition(...)}

② 模型请求时提取 schema
    schemas = registry.get_tool_schemas(["echo_tool"])
    # 返回 [{"type": "object", "properties": {"text": {"type": "string"}}}]
    # 塞进 LLM 请求的 "tools" 字段

③ 模型返回 tool_call 后执行
    context = ToolCallContext(tool_name="echo_tool", tool_args='{"text":"hello"}', ...)
    result = registry.execute_tool_call("echo_tool", '{"text":"hello"}', context)
    # → 沙箱校验 → 查工具 → JSON 解析 → 反射签名 → handler(text="hello") → ToolResult
    # 返回 ToolResult(ok=True, content="hello", metadata={"tool_name":"echo_tool"})

④ 每次 run 构建独立副本
    reg1 = build_run_registry(dispatcher, checker, waiter)  # run A
    reg2 = build_run_registry(dispatcher, checker, waiter)  # run B
    # reg1 和 reg2 互不影响（浅拷贝 self._tools 字典）
    # 但共享同一个 handler 函数对象（只读，不会互相污染）
~~~

## 10. ToolRunner — 工具并发执行引擎

异步路径（核心）：async_handle_tool_calls(registry, tool_calls, ...)

~~~树形
① 预分类 — build_tool_batch()
│
├── 遍历所有 tool_call，调 approval_checker(tool_name)
│   ├── 不需要审批 → item.requires_approval=False → 放入 ready_items
│   └── 需要审批   → item.requires_approval=True  → 放入 pending_items
│
└── pending_items → 调 on_approval_required() 创建审批单
    └── 往 pending_approvals 表写工单，返回 UUID 挂在 item.approval_id 上

② 播报 — yield assistant_tool_call event × N
    └── 前端展示"模型正在调用 read_file、write_file..."

③ 并发执行 — asyncio.gather(run_single_tool(item) for item in ready_items)

    run_single_tool(item):
    │
    ├── 白名单校验：tool_name 不在 allow_tool_names → 报错
    │
    ├── 构造 ToolCallContext
    │   ├── tool_name / tool_args / tool_call_id
    │   ├── session_id / run_id
    │   └── workspace_path / allow_tool_names / vfs
    │
    ├── terminal_execute_call():
    │   ├── on_tool_start → 写 ToolCallRecord(status="running")
    │   │
    │   ├── loop.run_in_executor(线程池, registry.execute_tool_call, name, args, context)
    │   │   ├── 工具在后台线程执行，不阻塞事件循环
    │   │   └── wait_for(timeout=120s) → 超时返回 timeout
    │   │
    │   └── on_tool_finish → 更新 ToolCallRecord(status + result_json)
    │
    └── pipeline.execute(context, terminal_execute_call)
        └── SandboxMiddleware 包裹工具调用（洋葱模型）
            前置：路径改写 + 安全校验 → next() → 后置：结果清理

④ 处理结果 — 等 gather 完成，逐个 yield event
│
├── tool_result is None  → timeout → yield RunEvent(type="tool_error")
├── tool_result.ok=True  → yield RunEvent(type="tool_result")
├── tool_result.ok=False → yield RunEvent(type="tool_error")
└── 构造 ChatMessage(role="tool", tool_call_id, content) → 发回模型

⑤ 审批中断检查
│
├── pending_items 非空 → 还有工具没批
│   ├── yield approval_required event × N
│   └── return ToolBatchResult(paused_for_approval=True)
│       └── AgentRunner 收到 → break → PAUSED
│
└── pending_items 为空 → 全跑完了
    └── return ToolBatchResult(paused_for_approval=False)
        └── AgentRunner 收到 → continue → 下一轮 LLM 调用

────────────────────────────────────────────────────

同步路径（无需审批的简单场景）：

~~~树形
handle_tool_calls(registry, tool_calls, allow_tool_names, event_index)

for tool_call in tool_calls:                    ← 顺序执行，不并发
│
├── ① yield RunEvent(type="assistant_tool_call", content=arguments)
├── ② 白名单校验 → 不通过抛 ValueError
├── ③ 构造 ToolCallContext
├── ④ registry.execute_tool_call(name, arguments, context)
├── ⑤ yield tool_result / tool_error event
└── ⑥ 构造 ChatMessage(role="tool", ...)

返回 ToolBatchResult(events, tool_messages, next_event_index)

────────────────────────────────────────────────────

具体例子 — 异步路径：

用户: "帮我读 README 并删掉 temp.txt"

LLM 返回:
    tool_call(read_file, "README.md")   ← SAFE，不需要审批
    tool_call(delete_file, "temp.txt")  ← DANGEROUS，需要审批

async_handle_tool_calls(registry, tool_calls, ...):

① build_tool_batch:
    ├── read_file   → requires_approval=False → ready_items[0]
    └── delete_file → requires_approval=True  → pending_items[0]
        └── on_approval_required → INSERT pending_approvals → approval_id="AP-007"

② yield:
    RunEvent(assistant_tool_call, "read_file")
    RunEvent(assistant_tool_call, "delete_file")

③ asyncio.gather( run_single_tool(read_file) )  ← 只有 read_file 能跑
    ├── on_tool_start → ToolCallRecord 写入 running
    ├── 线程池执行 → read_file("README.md") → "# 项目说明..."
    └── on_tool_finish → ToolCallRecord 更新 completed

④ yield RunEvent(tool_result, "read_file", "# 项目说明...")
   构造 ChatMessage(role="tool", call_001, "# 项目说明...")

⑤ pending_items = [delete_file] → 非空！
    yield RunEvent(approval_required, "delete_file", content="AP-007")
    return ToolBatchResult(paused_for_approval=True)

→ AgentRunner break → PAUSED，前端弹出审批框："是否允许删除 temp.txt？"

## 11. ResumeRunService — 审批恢复执行

~~~树形
入口：resume_run(approval_id, rejected=False)

触达路径：
POST /approvals/{approval_id}/approve → ResumeRunService.resume_run(approval_id, rejected=False)
POST /approvals/{approval_id}/reject  → ResumeRunService.resume_run(approval_id, rejected=True)

────────────────────────────────────────────────────

阶段一：重建上下文

① 读取审批工单
├── approval = approval_store.get(approval_id)
│   └── 拿到：session_id, run_id, batch_id, tool_name, tool_call_id, arguments, event_index
│
├── messages = approval_store.restore_messages(approval)
│   └── 从 approval.saved_messages 反序列化出 pause 时的对话历史
│
└── state = RunState(messages=messages)
    └── 用恢复的 messages 构建 state，不是从 session_records 读

② 加载 Agent 定义
├── 查 SessionRunRecord → agent_name
├── AgentDefinitionService.load_definition(agent_name)
│   └── 拿到 system_prompt + tool_names 白名单
└── 注意：resume 时不用原 run 的 agent_runner，而是重建

③ 构建工具运行时
├── tool_registry = build_run_registry(空回调)
│   └── resume 时不支持子 Agent（回调为空 lambda）
├── model_adapter = RunContextFactory.create_adapter(session_id)
│   └── 从 session 配置重建 adapter（同正常 run）
├── session_record = session_store.load_record(session_id)
│   └── 拿 workspace_path + permission_profile
└── approval_policy = _resolve_approval_policy(session_record)

────────────────────────────────────────────────────

阶段二：执行审批结果

④ 执行被审批的工具
│
├── rejected=True → 构造失败结果
│   ├── content = "[TOOL_REJECTED] 用户拒绝了此工具调用"
│   └── tr = ToolResult(ok=False, content=content)
│
└── rejected=False → 真正执行工具
    ├── 构建 MiddlewarePipeline([SandboxMiddleware()])
    ├── 构造 ToolCallContext（含 workspace_path + VFS）
    ├── terminal_execute_call()
    │   └── tool_registry.execute_tool_call(name, arguments, context)
    └── await pipeline.execute(...) 拿回 tool_result

⑤ 构造 tool_result event
├── event_index = approval.event_index  ← 从断点序号继续
├── RunEvent(type="tool_result", tool_name, tool_call_id, tool_result)
├── state.messages.append(ChatMessage(role="tool", ...))
└── yield "resume" 帧 + "run_event" 帧给前端

────────────────────────────────────────────────────

阶段三：判断是否继续

⑥ 刷新剩余审批单的快照
└── refresh_pending_saved_messages_for_batch(batch_id, state.messages, event_index)
    └── 同一批的其他 pending 审批单拿到最新的对话上下文

⑦ 关键分支：同一批还有待审批的吗？
│
├── is_batch_fully_resolved(batch_id) == False → 还有 pending
│   ├── finalize_run(PAUSED, events=[tool_result], is_resume=True)
│   │   └── append_run_events_partial → 追加 tool_result event
│   ├── yield "paused" 帧（带下一个 approval_id）
│   └── return ← 不继续模型推理，等用户批下一个
│
└── is_batch_fully_resolved(batch_id) == True → 全批完了
    └── 继续往下走 ↓

────────────────────────────────────────────────────

阶段四：拉起模型继续跑

⑧ 构造 AgentRunner（同正常 run 的构造流程）
├── state → 从 approval 恢复的 state（已含 user + assistant(tool_call) + tool）
├── agent_profile → 重建的 AgentDefinition
├── model_adapter → 重建的 adapter
├── tool_registry → 重建（不含子 Agent 功能）
└── approval_policy → 从 session 重建

⑨ 构造 RunLifecycleParams
├── skip_user_message=True       ← 关键！user message 已在 state 里
├── is_resume=True               ← 关键！追加模式
├── event_index=event_index      ← 关键！从断点序号接着排
├── initial_events=[tool_result] ← 关键！把刚才执行的 tool_result 带进循环
└── run_id=approval.run_id       ← 复用 pause 时的 run_id

⑩ RunLifecycle.iterate() → 同正常 run 的循环
├── AgentRunner 收到 state: [user, assistant(tool_call), tool(result)]
├── LLM 继续推理 → 可能又调工具 → 又触发 PAUSED
├── 或者直接回复 → COMPLETED
└── 终态落库 → 同正常流程

────────────────────────────────────────────────────

与正常 run 的对比：

|          | 正常 run                        | resume run                     |
|----------|--------------------------------|-------------------------------|
| state    | 读 session_records              | 读 approval.saved_messages      |
| run_id   | 新生成                          | 复用 pause 时的                 |
| 入口     | AgentRunner.async_stream_run    | 先手动执行工具，再进 AgentRunner |
| user msg | skip=False → AgentRunner 追加   | skip=True → 已经在 state 里     |
| 序号     | event_index=0                   | event_index=断点                |
| 初始事件 | initial_events=[]               | initial_events=[tool_result]   |
| 落库模式 | is_resume=False → 新建 run 行   | is_resume=True → 追加 events   |

一条 run 可能经历多次 resume：
  run 启动 → PAUSED → resume → PAUSED → resume → ... → COMPLETED
  每次暂停都落库，每次恢复都追加，event_index 不断递增，最终拼成完整轨迹

────────────────────────────────────────────────────

具体例子 — 用户说"删掉 a.py 和 b.py"：

① 正常 run 启动
   用户: "删掉 a.py 和 b.py"
   LLM → tool_call(delete_file, "a.py") + tool_call(delete_file, "b.py")
   两个都是 DANGEROUS → 都进 pending_items → 创建 AP-1, AP-2
   → PAUSED，前端弹出两个审批按钮

   session_run_events:
   ┌────┬──────────────────┬───────────┐
   │ 0  │ assistant_tool.. │ delete_f  │ a.py
   │ 1  │ assistant_tool.. │ delete_f  │ b.py
   │ 2  │ approval_required│ delete_f  │ AP-1
   │ 3  │ approval_required│ delete_f  │ AP-2
   └────┴──────────────────┴───────────┘

② 用户批准 AP-1 (a.py)
   resume_run("AP-1", rejected=False):
   │
   ├── 从 approval.saved_messages 恢复 state:
   │   [user("删掉 a.py 和 b.py"), assistant(tool_calls=[delete_file:a, delete_file:b])]
   │
   ├── 真正执行 delete_file("a.py") → ToolResult(ok=True, "a.py 已删除")
   ├── yield tool_result event (event_index=4)
   │
   ├── refresh pending: AP-2 的 saved_messages 刷新（含 tool_result(a.py)）
   ├── is_batch_fully_resolved("batch-01")? AP-2 还是 pending → NO
   │
   └── finalize_run(PAUSED, is_resume=True) → append 第 5 条 event → return

   session_run_events:
   ┌────┬──────────────────┬───────────┐
   │ 4  │ tool_result      │ delete_f  │ a.py 已删除  ← 新增
   └────┴──────────────────┴───────────┘
   前端: 还剩 b.py 待审批

③ 用户批准 AP-2 (b.py)
   resume_run("AP-2", rejected=False):
   │
   ├── 从 approval.saved_messages 恢复 state:
   │   [user, assistant(tool_calls), tool("a.py 已删除")]
   │   ↑ 注意：state 已包含上一轮的 tool_result（refresh 刷新的）
   │
   ├── 真正执行 delete_file("b.py") → ToolResult(ok=True, "b.py 已删除")
   ├── yield tool_result event (event_index=5)
   │
   ├── is_batch_fully_resolved("batch-01")? YES！
   │
   ├── 构造 AgentRunner(state=[user, assistant(tool_calls), tool(a), tool(b)])
   ├── RunLifecycle.iterate():
   │   LLM 第 2 轮: 收到两个 tool_result → 回复 "a.py 和 b.py 已删除"
   │   → final_answer (event_index=6)
   │   → COMPLETED
   │
   └── finalize_run(COMPLETED, is_resume=True):
       append_events → 追加 tool_result(b.py) + final_answer + UPDATE reply

   session_run_events 最终:
   ┌────┬──────────────────┬───────────┐
   │ 0  │ assistant_tool.. │ delete_f  │ a.py
   │ 1  │ assistant_tool.. │ delete_f  │ b.py
   │ 2  │ approval_required│ delete_f  │ AP-1
   │ 3  │ approval_required│ delete_f  │ AP-2
   │ 4  │ tool_result      │ delete_f  │ a.py 已删除    ← resume 1
   │ 5  │ tool_result      │ delete_f  │ b.py 已删除    ← resume 2
   │ 6  │ final_answer     │ (null)    │ 两个文件已删除  ← resume 2
   └────┴──────────────────┴───────────┘

   session_runs(abc123):
   ├── event_count: 7
   ├── reply: "两个文件已删除"
   └── status: "completed"
~~~
## 速查表

~~~树形
完整调用链

POST /run/stream → RunService.stream()
│
├── ① RunContextFactory.assemble()
│   ├── 查 SessionRecord → ProviderConfig + ModelSetting → 构建 adapter
│   ├── 读旧 state → HistoryCompactor.auto_compact → 压缩后 state
│   ├── AgentDefinition → ContextAssembler（AGENTS.md + skill）→ 合并 system_prompt
│   └── → RunContext{state, agent_profile, adapter, policy, workspace, session_type}
│
├── ② ToolTracer(db, run_store, approval_store, session_id, run_id)
│   └── on_tool_start / on_tool_finish / on_approval_required
│
├── ③ AgentRunner(state, agent_profile, adapter, tool_registry, policy)
│
├── ④ RunSSEBridge.stream()
│   ├── yield "start" {run_id}
│   └── RunLifecycle.iterate()
│       ├── 收到 str            → reply_text+=item → yield TextDeltaItem → SSE "delta"
│       ├── 收到 thinking_delta → thinking_buf+=item → yield ThinkingDeltaItem → SSE "thinking_delta"
│       ├── 收到 RunEvent
│       │   ├── tool_result / tool_error → reply_text=""
│       │   └── flush thinking → events.append → yield
│       └── 终态 → persist.finalize_run() → 落库 + VFS → yield "end"/"paused"
│
├── ⑤ AgentRunner.async_stream_run() — while True 循环
│   ├── build_model_request() → adapter.async_stream_generate()
│   │   ├── thinking_delta → yield 给 RunLifecycle
│   │   ├── content_delta  → yield 出去 + 攒进 raw_reply_chunks
│   │   ├── tool_call_delta → 按 index 攒进 tool_call_buffers
│   │   └── done(usage)    → 存 self.last_usage
│   ├── finish_reason == "tool_calls"
│   │   ├── 拼 ToolCall → 构造 assistant（content + tool_calls）
│   │   ├── yield assistant_text event（lead-in 非空时）
│   │   ├── async_handle_tool_calls() → 审批预检 → 并发执行 → ToolBatchResult
│   │   ├── state.messages 追入 tool_messages → paused? → break : continue
│   │   └── continue 下一轮
│   └── finish_reason == "stop"
│       ├── build_reply() → final_answer event
│       ├── state.messages.append(assistant)
│       └── break
│
├── ⑥ ChatCompletionsAdapter
│   ├── 构造 HTTP：headers + payload（model, messages, stream:true, tools, extra_payload）
│   ├── httpx.stream("POST") + 重试 3 次（1s→2s→4s）
│   └── aiter_lines() → choice[0].delta + finish_reason → _parse_delta()
│       ├── reasoning_content / thinking_content / reasoning → thinking_delta
│       ├── content           → content_delta
│       ├── tool_calls        → tool_call_delta（存整个原始 delta）
│       └── 空                → done
│
└── ⑦ 落库：RunRecorder.finalize_run()
    ├── COMPLETED → save_run_trace(reply) + save_state(state) + VFS.commit
    ├── PAUSED    → save_partial_run（不注入空消息）
    ├── CANCELLED → save_partial_run + 补 assistant（流中断时）+ VFS.discard
    └── FAILED    → save_partial_run + 补 assistant（流中断时）+ VFS.discard

────────────────────────────────────────────────────

RunEvent 7 种

├── assistant_text       工具前文字              content = lead-in 文本
├── assistant_tool_call  工具调用启动             content = 工具参数 JSON
├── tool_result          工具执行成功             content = 结果文本
├── tool_error           工具执行失败/超时         content = 错误消息
├── final_answer         模型最终回答             content = 答案文本
├── approval_required    需要人工审批             content = approval_id
└── thinking             思考收束块               content = 思考全文

StreamChunk 4 种

├── thinking_delta       思考增量                 thinking_delta = 文本
├── content_delta        正文增量                 content_delta = 文本 + finish_reason
├── tool_call_delta      工具调用增量              tool_call_delta = 整个原始 delta
└── done                 流结束                   finish_reason 或 usage

state.messages 累加

user
  → assistant(content=lead-in, tool_calls=[...])
    → tool × N（每个 tool 绑定 tool_call_id）
      → ...（多轮循环）
        → assistant(content=最终回答)
          → break

## 12. MCP / A2A / RAG — 从零理解与项目接入

这一章先不写代码，先把概念拆开。

三个词不是同一层东西：

| 名称 | 它是什么 | 解决什么问题 | 放在项目哪一层 |
|------|----------|--------------|----------------|
| MCP | 工具 / 上下文接入协议 | Agent 怎么连接外部工具、文件、数据库、服务 | Tool Platform / Runtime |
| A2A | Agent 和 Agent 通信协议 | 多个 Agent 怎么互相发现、分工、传任务、交结果 | Multi-Agent Orchestration |
| RAG | 检索增强生成方法 | 模型回答前怎么查自己的知识库 / 项目文档 | Context / Knowledge |

一句话：

~~~树形
RAG 负责：查知识
MCP 负责：接工具
A2A 负责：Agent 协作
~~~

────────────────────────────────────────────────────

### 12.1 最基础前置概念

~~~树形
LLM
├── 含义：大语言模型
├── 示例：GPT、Claude、Gemini、Qwen
└── 能力：根据 messages 生成下一段文本，或生成 tool_calls

Agent
├── 含义：带目标、上下文、工具、循环控制的大模型运行体
├── 比普通 LLM 多了：
│   ├── system_prompt      → 行为规则
│   ├── tools              → 可调用工具
│   ├── memory / session   → 对话状态
│   ├── workspace          → 当前项目目录
│   └── trace              → 执行过程记录
└── 在本项目里大致对应：
    ├── AgentDefinition
    ├── RunContext
    ├── AgentRunner
    ├── ToolRegistry
    └── RunRecorder

Tool Calling
├── 含义：模型不直接做事，而是生成一个工具调用请求
├── 示例：模型生成 read_file({"path":"README.md"})
├── Runtime 执行真实 Python 函数
└── 执行结果再作为 role="tool" 消息交回模型

Protocol
├── 含义：通信约定
├── 规定：
│   ├── 请求怎么写
│   ├── 响应怎么写
│   ├── 错误怎么写
│   ├── 身份怎么表达
│   └── 能力怎么暴露
└── MCP / A2A 都是协议，RAG 不是协议
~~~

────────────────────────────────────────────────────

### 12.2 MCP — Model Context Protocol

最基础理解：

~~~树形
没有 MCP：

Agent
├── 直接接 GitHub API
├── 直接接 Notion API
├── 直接接 数据库 API
├── 直接接 浏览器 API
└── 每接一个系统，都要写一套特殊适配

问题：
├── 工具接入越来越乱
├── 每个模型 / Agent 都要重复适配
├── 权限、审计、错误格式不好统一
└── 工具来源不清晰

有 MCP：

Agent / App
└── MCP Client
    ├── 连接 MCP Server A → 暴露 filesystem tools
    ├── 连接 MCP Server B → 暴露 browser tools
    ├── 连接 MCP Server C → 暴露 database tools
    └── 连接 MCP Server D → 暴露 company API tools

好处：
├── Agent 只理解 MCP 统一接口
├── 外部系统由 MCP Server 封装
├── 工具发现、调用、返回更标准
└── 后续可以插拔更多工具
~~~

官方核心意思：

~~~树形
MCP = AI 应用连接外部系统的开放标准

外部系统包括：
├── 本地文件
├── 数据库
├── 搜索引擎
├── 浏览器
├── SaaS 应用
├── 公司内部 API
└── 专门工作流
~~~

MCP 里几个关键角色：

~~~树形
MCP Host
├── 含义：承载 Agent 的应用
├── 示例：Codex、Claude Desktop、Cursor、你的 AGENT Build
└── 负责：管理用户会话、模型、权限、UI

MCP Client
├── 含义：Host 里负责连接某个 MCP Server 的客户端
├── 一个 server 通常对应一个 client 连接
└── 负责：
    ├── 启动 / 连接 server
    ├── 请求 tool list
    ├── 调用 tool
    ├── 接收 tool result
    └── 把错误翻译回 runtime

MCP Server
├── 含义：外部工具 / 数据源的适配服务
├── 示例：
│   ├── filesystem server
│   ├── github server
│   ├── postgres server
│   └── browser server
└── 负责：
    ├── 声明自己有哪些 tools
    ├── 接收 tool call
    ├── 执行真实动作
    └── 返回标准结果

MCP Tool
├── 含义：server 暴露给 Agent 的一个可调用能力
├── 示例：read_file / search_repo / query_database
└── 注意：tool 不是 server，server 可以暴露多个 tools
~~~

MCP 和普通 tool calling 的关系：

~~~树形
普通本地工具：

ToolRegistry
└── "read_file" → Python handler()

MCP 工具：

ToolRegistry
└── "mcp.github.search_issues"
    └── MCPToolBridge
        └── MCPClient.call_tool(server="github", tool="search_issues", args)
            └── GitHub MCP Server 真正执行

结论：
├── Agent 仍然只看到 tool
├── Runtime 内部区分 local tool / MCP tool
└── MCP 不应该直接塞进 AgentDefinition
~~~

MCP 在本项目里的推荐接入位置：

~~~树形
当前项目已有：

AgentRunner
└── async_handle_tool_calls()
    └── ToolRegistry
        ├── 本地工具 read_file
        ├── 本地工具 write_file
        ├── 本地工具 spawn_child_agent
        └── ...

接入 MCP 后：

AgentRunner
└── async_handle_tool_calls()
    └── ToolRegistry
        ├── 本地工具 read_file
        ├── 本地工具 write_file
        ├── MCP 工具 github.search_issues
        ├── MCP 工具 browser.open_page
        └── MCP 工具 rag.search_docs

关键原则：
├── 不改 AgentRunner 主循环
├── 不推翻 ToolRegistry
├── 不让 AgentDefinition 直接管理 MCP server
├── MCP tool 映射进统一工具入口
└── trace / approval / timeout 继续复用现有链路
~~~

MCP 最小接入链路：

~~~树形
① 配置 MCP server
│
├── mcp_servers.github
│   ├── enabled: true
│   ├── transport: "stdio" 或 "http"
│   ├── command / args / env
│   ├── url / http_headers
│   ├── startup_timeout
│   ├── tool_timeout
│   ├── enabled_tools
│   └── disabled_tools
│
② 启动 / 连接 MCP server
│
├── stdio → 本地启动一个进程
└── http  → 连接远程服务 URL
│
③ tool discovery
│
├── server 返回 tool list
├── 每个 tool 有 name / description / input_schema
└── runtime 记录来源 server_id
│
④ 映射到 ToolRegistry
│
├── 本地包装成 MCPToolDefinition
├── name 可以加前缀避免冲突
│   └── 示例："github.search_issues"
└── handler 不是真实业务函数，而是 MCP client call
│
⑤ Agent 调用工具
│
├── 模型生成 tool_call
├── ToolRegistry 找到 MCP wrapper
├── MCP wrapper 调 server.call_tool()
└── 结果转成统一 ToolResult
│
⑥ trace / audit
│
├── 记录 tool_name
├── 记录 server_id
├── 记录 arguments
├── 记录 result / error
└── 前端 ToolCard 正常显示
~~~

MCP 设计边界：

| 问题 | 放哪里 |
|------|--------|
| server 怎么启动 | MCP config / MCP client adapter |
| server 暴露哪些 tools | MCP discovery |
| tool 是否允许给 Agent 用 | enabled_tools / disabled_tools + Agent tool_names |
| tool 调用超时 | MCP client adapter 或 ToolRunner 外层 |
| tool 是否需要审批 | 统一 ToolRunner / Middleware |
| tool 结果怎么展示 | 统一 RunEvent / Trace |
| tool 错误怎么返回 | 统一 ToolResult(ok=False) |

────────────────────────────────────────────────────

### 12.3 RAG — Retrieval-Augmented Generation

最基础理解：

~~~树形
普通 LLM 回答：

用户问题
└── LLM 直接根据训练记忆回答

问题：
├── 模型不知道你的私有项目文档
├── 模型知识可能过期
├── 模型可能编造
└── 回答缺少来源

RAG 回答：

用户问题
├── 先去知识库检索相关资料
├── 把检索结果塞进上下文
└── LLM 基于这些资料回答

核心变化：
模型不是凭空答，而是先查资料再答
~~~

RAG 不是一个工具名，而是一条链路：

~~~树形
RAG Pipeline

① 文档收集
├── README.md
├── docs/*.md
├── specs/*.md
├── 代码注释
└── 数据库记录

② 文档切片 chunking
├── 长文档切成小段
├── 每段保留来源路径
├── 每段保留标题 / 行号
└── 每段不要太长

③ 向量化 embedding
├── 把文本变成数字向量
├── 相似文本向量距离更近
└── 存入 vector store

④ 检索 retrieval
├── 用户问题也转成向量
├── 去 vector store 找最相似 chunks
└── 取回 top_k 个结果

⑤ 重排 rerank（可选）
├── 用更精细模型重新排序
└── 把最相关内容放前面

⑥ 上下文组装
├── 拼成引用材料
├── 限制 token 数量
└── 注入 system prompt 或 user prompt

⑦ 生成答案
├── LLM 阅读材料
├── 回答用户
└── 附带来源路径
~~~

RAG 中常见对象：

~~~树形
Document
├── 含义：原始文档
└── 示例：docs/Python基础操作.md

Chunk
├── 含义：文档切出来的一小段
├── content: 文本内容
└── metadata:
    ├── path
    ├── title
    ├── line_start
    └── line_end

Embedding
├── 含义：文本对应的一组数字
├── 示例：[0.12, -0.03, 0.88, ...]
└── 用途：计算语义相似度

Vector Store
├── 含义：存 chunk + embedding 的数据库
├── 示例：Chroma / FAISS / LanceDB / pgvector
└── 用途：快速找相似内容

Retriever
├── 含义：检索器
├── 输入：query
└── 输出：相关 chunks

Reranker
├── 含义：重排器
├── 输入：query + candidate chunks
└── 输出：更准确的排序
~~~

RAG 在本项目里的推荐接入方式：

~~~树形
方案 A：作为 ContextAssembler 的一部分

RunContextFactory.assemble()
└── ContextAssembler.assemble()
    ├── AGENTS.md
    ├── skill catalog
    ├── workspace context
    └── RAG 检索结果

优点：
├── 模型每轮自动拿到相关知识
├── 适合项目文档、规则、长期记忆
└── 用户不需要显式调用 search

风险：
├── 每轮都检索，成本更高
├── 检索结果可能污染上下文
└── token 控制更复杂

────────────────────────────────────────────────────

方案 B：作为一个工具 rag_search

AgentRunner
└── ToolRegistry
    └── rag_search(query, top_k)
        └── RAGService.search()

优点：
├── 模型需要时才查
├── trace 里能看到查了什么
├── 可审批 / 可限流
└── 容易先做 MVP

风险：
├── 模型可能忘记调用
└── 需要 prompt 教它什么时候查

────────────────────────────────────────────────────

方案 C：RAG 包成 MCP Server

AgentRunner
└── ToolRegistry
    └── mcp.rag.search_docs
        └── MCP Client
            └── RAG MCP Server
                └── Vector Store

优点：
├── RAG 能独立成服务
├── 其他 Agent / App 也能复用
├── 符合 MCP 工具接入方向
└── 后续扩展更干净

风险：
├── 比方案 B 多一层协议
└── 初期实现成本更高
~~~

本项目建议顺序：

~~~树形
第一阶段：先做 rag_search 本地工具
├── 最小成本
├── 可复用现有 ToolRegistry
├── 可进入 trace
└── 方便验证检索质量

第二阶段：把 rag_search 抽成 RAGService
├── index_docs()
├── search(query)
├── format_context(chunks)
└── refresh_index()

第三阶段：再包装成 MCP Server
├── 给本项目用
├── 给其他 Agent 用
└── 为 A2A 多 Agent 共享知识做准备
~~~

RAG 最小 MVP 数据流：

~~~树形
用户问："TASK-054 里 MCP 应该怎么接？"
│
├── Agent 判断需要查项目资料
│
├── 调用 rag_search({
│     "query": "TASK-054 MCP 接入边界",
│     "top_k": 5
│   })
│
├── RAGService.search()
│   ├── query → embedding
│   ├── vector_store.similarity_search()
│   └── 返回相关 chunks
│
├── 工具返回：
│   ├── docs / specs 里的相关片段
│   ├── 文件路径
│   └── 行号
│
├── LLM 基于片段回答
│
└── 前端 Trace 显示：
    ├── tool_call: rag_search
    ├── query: "TASK-054 MCP 接入边界"
    └── result: 命中文档列表
~~~

────────────────────────────────────────────────────

### 12.4 A2A — Agent2Agent

最基础理解：

~~~树形
没有 A2A：

一个主 Agent
├── 自己规划
├── 自己查资料
├── 自己写代码
├── 自己测试
└── 自己 review

问题：
├── 单个 Agent 上下文压力大
├── 专业能力混在一起
├── 长任务容易乱
└── 不同系统里的 Agent 难协作

有 A2A：

Main Agent
├── 找 Planner Agent 拆任务
├── 找 Research Agent 查资料
├── 找 Coder Agent 写代码
├── 找 Reviewer Agent 审查
└── 汇总结果给用户

核心变化：
Agent 不再只是工具，而是能以 Agent 身份协作
~~~

A2A 关键对象：

~~~树形
Agent Card
├── 含义：Agent 的能力名片
├── 通常是 JSON
└── 描述：
    ├── 这个 Agent 叫什么
    ├── 会做什么
    ├── 支持哪些输入输出形式
    ├── 怎么连接
    └── 需要什么认证

Client Agent
├── 含义：发起任务的 Agent
├── 示例：Main Agent
└── 负责：
    ├── 发现可用 Agent
    ├── 选择合适 Agent
    ├── 发任务
    ├── 接收状态
    └── 汇总 artifact

Remote Agent
├── 含义：被调用的 Agent
├── 示例：Reviewer Agent
└── 负责：
    ├── 接收任务
    ├── 执行任务
    ├── 回报进度
    └── 返回 artifact

Task
├── 含义：一次跨 Agent 协作任务
├── 有生命周期：
│   ├── submitted
│   ├── working
│   ├── input_required
│   ├── completed
│   ├── failed
│   └── cancelled
└── 适合长任务

Artifact
├── 含义：Remote Agent 交付的结果
├── 示例：
│   ├── 一份 review 报告
│   ├── 一段代码补丁
│   ├── 一个检索摘要
│   └── 一个设计方案
~~~

A2A 和本项目现有子 Agent 的关系：

~~~树形
当前项目已有内部子 Agent：

Main Run
└── spawn_child_agent 工具
    ├── 创建 child run
    ├── 查询 child status
    └── 等待 child result

这是“项目内部多 Agent”

────────────────────────────────────────────────────

A2A 是“跨系统 / 跨框架多 Agent”

Main Agent
└── A2A Client
    ├── 发现外部 Agent Card
    ├── 给远程 Agent 发 Task
    ├── 接收状态更新
    └── 拿回 Artifact

区别：
├── spawn_child_agent 更像内部函数 / 内部服务
├── A2A 更像标准化网络协议
├── 内部子 Agent 可以先跑通
└── 后续再把它暴露成 A2A Remote Agent
~~~

A2A 和 MCP 的区别：

| 对比项 | MCP | A2A |
|--------|-----|-----|
| 连接对象 | 工具 / 数据源 / 外部系统 | 另一个 Agent |
| 调用方式 | call_tool | send_task / message |
| 返回结果 | tool result | task status + artifact |
| 任务长度 | 通常较短，也可异步 | 更适合长任务 |
| 是否暴露内部状态 | 不需要 | 不需要 |
| 本项目优先级 | 高 | 较后 |

简单判断：

~~~树形
如果对方只是一个函数能力 → 用 MCP / tool
如果对方是能自己规划和执行的智能体 → 用 A2A
~~~

A2A 在本项目里的推荐接入顺序：

~~~树形
第一阶段：继续完善内部子 Agent
├── spawn_child_agent
├── child run trace
├── child status
└── child result

第二阶段：定义本项目自己的 Agent Card
├── name
├── description
├── skills
├── input modes
├── output modes
└── endpoint

第三阶段：把本项目 Agent 暴露成 A2A Server
├── 外部系统能发现本项目 Agent
├── 外部系统能提交 task
├── 本项目能返回 status
└── 本项目能返回 artifact

第四阶段：实现 A2A Client
├── 本项目能发现外部 Agent
├── 本项目能调用外部 Agent
├── 外部 Agent 结果进入 trace
└── 前端显示远程 Agent 执行状态
~~~

不建议现在立刻做 A2A 的原因：

~~~树形
A2A 依赖：
├── 稳定的 Agent runtime
├── 稳定的 task / run 生命周期
├── 稳定的 trace
├── 稳定的权限模型
├── 稳定的工具层
└── 清晰的 Agent 能力边界

如果基础没稳就做 A2A：
├── 调试困难
├── 状态同步复杂
├── 错误来源不清
└── 容易把内部架构绑死
~~~

────────────────────────────────────────────────────

### 12.5 三者组合后的完整架构

~~~树形
用户
│
└── 前端 UI
    │
    └── POST /run/stream
        │
        └── RunService
            │
            ├── RunContextFactory
            │   ├── 读取 session
            │   ├── 读取 agent definition
            │   ├── 组装 AGENTS.md / skill
            │   └── 可选：RAG 自动检索上下文
            │
            ├── AgentRunner
            │   ├── 调 LLM
            │   ├── 收 tool_calls
            │   └── 调 ToolRegistry
            │
            ├── ToolRegistry
            │   ├── Local Tools
            │   │   ├── read_file
            │   │   ├── write_file
            │   │   └── spawn_child_agent
            │   │
            │   ├── MCP Tools
            │   │   ├── github.search_issues
            │   │   ├── browser.open_page
            │   │   └── rag.search_docs
            │   │
            │   └── A2A Tools / Bridge（后期）
            │       ├── discover_agent
            │       ├── send_task
            │       └── get_task_status
            │
            ├── RunLifecycle
            │   ├── 流式输出 delta
            │   ├── 流式输出 run_event（tool_call / tool_result / tool_error）
            │   ├── 处理 approval_required
            │   └── 处理 paused / completed / failed
            │
            └── RunRecorder
                ├── 保存 run
                ├── 保存 events
                ├── 保存 tool calls
                └── 保存最终 state
~~~

一个真实例子：

~~~树形
用户说：
"根据项目 TASK-054，帮我设计 MCP 接入方案，并找一个 reviewer 检查。"

可能发生：

① Main Agent 收到问题
│
├── 判断需要查项目文档
│
② 调用 RAG
│
├── rag_search("TASK-054 MCP 接入方案")
├── 返回 specs/TASK-054.md 相关片段
└── Main Agent 理解项目边界
│
③ 调用 MCP 工具
│
├── 可能调用 filesystem / git / docs 工具
└── 获取更多上下文
│
④ 调用内部子 Agent 或 A2A Agent
│
├── Reviewer Agent 检查方案
└── 返回 artifact: review_report
│
⑤ Main Agent 汇总
│
├── 给出方案
├── 给出风险
├── 给出下一步任务切片
└── 前端 Trace 展示完整过程
~~~

────────────────────────────────────────────────────

### 12.6 接入本项目的最小路线图

不要一口气做完。按最小切片推进。

~~~树形
推荐顺序：

第 1 步：MCP 配置模型
├── 只定义 mcp_servers.<id>
├── 不连接真实 server
├── 不暴露给 Agent
└── 目标：边界清楚

第 2 步：MCP discovery
├── 能启动 / 连接一个 server
├── 能拿到 tool list
├── 能保存 server_id + tool name + schema
└── 目标：知道外部有哪些工具

第 3 步：MCP Tool Bridge
├── 把 discovered tool 包成 ToolRegistry 可执行工具
├── 调用后返回统一 ToolResult
├── 错误进入 tool_error
└── 目标：Agent 像调用本地工具一样调用 MCP 工具

第 4 步：RAG 本地工具
├── 先索引 docs / specs
├── 做 rag_search
├── 返回 path + snippet
└── 目标：Agent 能查项目知识

第 5 步：RAG MCP Server
├── 把 rag_search 变成 MCP server 暴露的 tool
├── 本项目通过 MCP 调它
└── 目标：知识检索工具标准化

第 6 步：A2A 内部能力对齐
├── 整理 Agent Card 草案
├── 把内部 child agent 的能力描述清楚
└── 目标：先知道自己能对外暴露什么

第 7 步：A2A Server / Client
├── Server：别人能调用我
├── Client：我能调用别人
└── 目标：跨系统 Agent 协作
~~~

当前项目最合理的优先级：

| 优先级 | 能力 | 原因 |
|--------|------|------|
| P0 | MCP server 配置边界 | 已有 TASK-054 方向，和 ToolRegistry 强相关 |
| P1 | MCP tool bridge | 能直接增强工具生态 |
| P1 | RAG 本地工具 | 能让 Agent 理解项目文档，收益很高 |
| P2 | RAG MCP 化 | 等本地 RAG 跑通后再标准化 |
| P3 | A2A | 等内部 Agent 生命周期稳定后再做 |

────────────────────────────────────────────────────

### 12.7 最小文件边界草案

这里只是学习笔记，不代表马上创建文件。

~~~树形
agent_prototype/mcp/
├── config.py
│   └── 负责：定义 MCPServerConfig
│
├── client.py
│   └── 负责：连接 MCP server，list_tools，call_tool
│
├── discovery.py
│   └── 负责：把 server 暴露的 tools 转成 DiscoveredMCPTool
│
└── bridge.py
    └── 负责：把 DiscoveredMCPTool 包成 ToolRegistry 能执行的工具

agent_prototype/rag/
├── document_loader.py
│   └── 负责：从 docs / specs / README 读取文档
│
├── chunker.py
│   └── 负责：把长文档切成 chunks
│
├── embeddings.py
│   └── 负责：把文本转成向量
│
├── store.py
│   └── 负责：保存 / 查询向量
│
└── service.py
    └── 负责：提供 index_workspace() 和 search()

agent_prototype/a2a/
├── agent_card.py
│   └── 负责：描述本项目 Agent 能力
│
├── server.py
│   └── 负责：接收外部 Agent task
│
├── client.py
│   └── 负责：调用外部 Agent
│
└── task_mapper.py
    └── 负责：A2A task 和本项目 run 互相转换
~~~

分层原则：

~~~树形
MCP 层
├── 只负责协议连接和工具发现
└── 不负责 Agent 推理

RAG 层
├── 只负责文档索引和检索
└── 不负责决定最终答案

A2A 层
├── 只负责跨 Agent 任务通信
└── 不负责本地工具执行细节

Runtime 层
├── 负责编排 LLM + tools + trace
└── 继续作为主链路中心
~~~

────────────────────────────────────────────────────

### 12.8 初学者最容易混淆的点

| 误解 | 正确理解 |
|------|----------|
| MCP 是一个工具 | MCP 是协议，MCP server 可以暴露多个工具 |
| RAG 是向量数据库 | 向量数据库只是 RAG 的一个组件 |
| A2A 是 tool calling | A2A 是 Agent 间任务协议，不只是函数调用 |
| 有 RAG 就不会幻觉 | RAG 只能降低幻觉，检索错了仍会答错 |
| MCP 会替代 ToolRegistry | 不应该替代，应该映射进统一工具入口 |
| A2A 越早做越好 | 不对，A2A 需要稳定 runtime 和 trace 做基础 |
| RAG 必须一开始就很复杂 | 不需要，先做 docs/specs 的本地检索即可 |

最小判断口诀：

~~~树形
要查知识 → RAG
要用外部工具 → MCP
要找另一个 Agent 干活 → A2A
~~~

────────────────────────────────────────────────────

### 12.9 和现有任务卡的关系

~~~树形
TASK-054
└── MCP Server 边界设计
    ├── 先定义 server config
    ├── Phase 1 只接 tools
    ├── 不接 resources / prompts
    └── 不直接改 AgentDefinition

TASK-055
└── MCP Server 配置加载与发现
    ├── 读取 mcp_servers 配置
    ├── 连接 server
    └── 发现 tool list

TASK-056
└── MCP Tool Bridge 与运行时接入
    ├── discovered tool → ToolRegistry
    ├── call_tool → ToolResult
    └── trace 记录 MCP 来源

RAG 后续可新增任务
└── 建议从 rag_search 本地工具开始

A2A 后续可新增任务
└── 建议等 child agent / run lifecycle 更稳定后开始
~~~

────────────────────────────────────────────────────

### 12.10 资料来源

~~~树形
MCP
├── 官方文档：https://modelcontextprotocol.io/docs/getting-started/intro
└── Anthropic / Linux Foundation 捐赠说明：
    https://www.anthropic.com/news/donating-the-model-context-protocol-and-establishing-of-the-agentic-ai-foundation

A2A
├── Google 发布说明：
│   https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/
├── Google Cloud 捐赠到 Linux Foundation：
│   https://developers.googleblog.com/en/google-cloud-donates-a2a-to-linux-foundation/
└── A2A GitHub：
    https://github.com/a2aproject/A2A

RAG
└── 原始论文：
    Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks
    https://arxiv.org/abs/2005.11401
~~~

## 13. 客服 Agent 业务工具设计

这一章对应岗位里的：

~~~树形
订单
物流
商品
售后
客服自动化闭环
~~~

先记住一句话：

~~~树形
客服 Agent 不是只会聊天
客服 Agent = 对话能力 + 业务工具 + 知识库 + 状态管理 + 人工兜底
~~~

────────────────────────────────────────────────────

### 13.1 为什么客服 Agent 必须有业务工具

普通聊天机器人：

~~~树形
用户："我的订单什么时候到？"
│
└── LLM 凭经验回答：
    "一般 3-5 天送达，请耐心等待。"

问题：
├── 不知道用户是谁
├── 不知道订单号
├── 不知道真实物流状态
├── 不能处理退款 / 售后
└── 容易答错
~~~

有业务工具的客服 Agent：

~~~树形
用户："我的订单什么时候到？"
│
├── Agent 判断需要查订单
│
├── tool_call: query_order(order_id)
│   └── 返回：订单状态、商品、付款状态
│
├── tool_call: query_logistics(order_id)
│   └── 返回：物流节点、预计送达时间
│
└── Agent 基于真实数据回答：
    "你的订单已发货，目前到达上海分拨中心，预计 6 月 17 日送达。"
~~~

核心区别：

| 类型 | 回答依据 | 是否能处理真实业务 |
|------|----------|--------------------|
| 普通聊天机器人 | 模型记忆 / prompt | 不能 |
| 客服 Agent | 工具返回的业务数据 | 能 |

────────────────────────────────────────────────────

### 13.2 客服场景里的常见工具

~~~树形
客服 Agent 工具集合

├── query_order
│   ├── 用途：查询订单详情
│   ├── 输入：order_id / user_id
│   └── 输出：订单状态、商品、金额、支付状态
│
├── query_logistics
│   ├── 用途：查询物流
│   ├── 输入：order_id / tracking_no
│   └── 输出：物流状态、物流节点、预计送达时间
│
├── query_product
│   ├── 用途：查询商品信息
│   ├── 输入：sku_id / product_name
│   └── 输出：库存、价格、规格、发货地
│
├── check_refund_policy
│   ├── 用途：判断是否符合退款规则
│   ├── 输入：order_id / reason
│   └── 输出：是否可退、原因、限制条件
│
├── create_after_sales_ticket
│   ├── 用途：创建售后工单
│   ├── 输入：order_id / issue_type / description
│   └── 输出：ticket_id、处理时限
│
├── transfer_to_human
│   ├── 用途：转人工
│   ├── 输入：reason / summary
│   └── 输出：queue_id / handoff_status
│
└── rag_search_policy
    ├── 用途：搜索客服规则 / FAQ / 售后政策
    ├── 输入：query
    └── 输出：相关规则片段 + 来源
~~~

────────────────────────────────────────────────────

### 13.3 工具不是随便写函数，要有稳定 I/O

错误设计：

~~~python
def query_order(x):
    return "查到了"
~~~

问题：

~~~树形
├── x 不清楚是什么
├── 返回值没有结构
├── 模型无法稳定理解
├── 前端无法展示
└── trace 无法分析
~~~

更合理的工具输入：

~~~json
{
  "order_id": "O202606150001",
  "user_id": "U1001"
}
~~~

更合理的工具输出：

~~~json
{
  "ok": true,
  "order": {
    "order_id": "O202606150001",
    "status": "shipped",
    "paid": true,
    "amount": 199.0,
    "items": [
      {
        "sku_id": "SKU-001",
        "name": "无线耳机",
        "quantity": 1
      }
    ]
  }
}
~~~

统一工具返回结构：

~~~树形
ToolResult
├── ok: bool
│   ├── true  → 工具成功
│   └── false → 工具失败
├── content: str
│   └── 给模型看的文本摘要
├── data: dict
│   └── 给系统 / 前端 / trace 用的结构化数据
└── error: optional
    └── 失败原因
~~~

────────────────────────────────────────────────────

### 13.4 订单工具 query_order

职责：

~~~树形
query_order
├── 负责：
│   ├── 根据 order_id 查询订单
│   ├── 校验订单是否属于当前用户
│   ├── 返回订单基础状态
│   └── 返回商品列表
│
└── 不负责：
    ├── 查询详细物流轨迹
    ├── 判断退款政策
    ├── 创建售后工单
    └── 生成最终客服话术
~~~

输入：

~~~json
{
  "order_id": "O202606150001"
}
~~~

输出：

~~~json
{
  "ok": true,
  "order_id": "O202606150001",
  "status": "shipped",
  "status_text": "已发货",
  "paid": true,
  "amount": 199.0,
  "created_at": "2026-06-14 20:10:00",
  "items": [
    {
      "sku_id": "SKU-001",
      "name": "无线耳机",
      "quantity": 1
    }
  ]
}
~~~

调用场景：

~~~树形
用户提到：
├── 我的订单
├── 订单状态
├── 是否发货
├── 能不能取消
├── 什么时候处理
└── order_id

Agent 应优先调用 query_order
~~~

失败场景：

~~~树形
订单不存在
├── ok=false
├── error_code="ORDER_NOT_FOUND"
└── Agent 提醒用户核对订单号

订单不属于当前用户
├── ok=false
├── error_code="ORDER_ACCESS_DENIED"
└── Agent 不能泄露订单信息

订单系统超时
├── ok=false
├── error_code="ORDER_API_TIMEOUT"
└── Agent 说明系统繁忙，可稍后重试或转人工
~~~

────────────────────────────────────────────────────

### 13.5 物流工具 query_logistics

职责：

~~~树形
query_logistics
├── 负责：
│   ├── 查询物流单号
│   ├── 查询物流节点
│   ├── 返回当前运输状态
│   └── 返回预计送达时间
│
└── 不负责：
    ├── 判断退款
    ├── 修改收货地址
    ├── 赔付决策
    └── 生成最终回答
~~~

输入：

~~~json
{
  "order_id": "O202606150001"
}
~~~

输出：

~~~json
{
  "ok": true,
  "tracking_no": "SF123456789",
  "carrier": "顺丰",
  "status": "in_transit",
  "status_text": "运输中",
  "estimated_delivery": "2026-06-17",
  "events": [
    {
      "time": "2026-06-15 08:30:00",
      "location": "上海分拨中心",
      "description": "快件到达分拨中心"
    }
  ]
}
~~~

物流异常：

~~~树形
常见异常
├── delayed         → 延迟
├── lost_suspected  → 疑似丢件
├── returned        → 已退回
├── address_error   → 地址异常
└── no_tracking     → 暂无轨迹

Agent 回答原则：
├── 明确当前状态
├── 说明可能原因
├── 给用户下一步
└── 必要时创建售后 / 转人工
~~~

────────────────────────────────────────────────────

### 13.6 售后工具 create_after_sales_ticket

售后工具比查询工具危险，因为它会改变业务状态。

职责：

~~~树形
create_after_sales_ticket
├── 负责：
│   ├── 创建售后工单
│   ├── 记录用户问题
│   ├── 选择售后类型
│   └── 返回 ticket_id
│
└── 不负责：
    ├── 私自承诺赔偿
    ├── 绕过退款规则
    ├── 直接改订单金额
    └── 直接关闭用户订单
~~~

输入：

~~~json
{
  "order_id": "O202606150001",
  "issue_type": "delivery_delayed",
  "description": "用户反馈物流超过预计时间未送达"
}
~~~

输出：

~~~json
{
  "ok": true,
  "ticket_id": "AS202606150001",
  "status": "created",
  "expected_response_hours": 24
}
~~~

审批策略：

~~~树形
低风险：
├── 查询订单
├── 查询物流
└── 查询商品

中风险：
├── 创建售后工单
└── 修改用户备注

高风险：
├── 退款
├── 赔付
├── 取消订单
└── 修改地址

建议：
├── 查询类工具无需审批
├── 创建工单可无需审批，但要留 trace
├── 退款 / 赔付必须审批或走规则引擎
└── 超出规则必须转人工
~~~

────────────────────────────────────────────────────

### 13.7 客服业务工具接入本项目

推荐先做 mock 工具，不直接接真实业务系统。

~~~树形
agent_prototype/tools/customer_service/
├── query_order.py
├── query_logistics.py
├── query_product.py
├── check_refund_policy.py
├── create_after_sales_ticket.py
└── transfer_to_human.py
~~~

进入现有链路：

~~~树形
AgentRunner
└── async_handle_tool_calls()
    └── ToolRegistry
        ├── query_order
        ├── query_logistics
        ├── query_product
        ├── check_refund_policy
        ├── create_after_sales_ticket
        └── transfer_to_human
~~~

前端视觉映射：

~~~树形
用户发问
│
├── 消息区显示 Agent 思考 / 回答
│
├── Trace / ToolCard 显示：
│   ├── query_order running
│   ├── query_order completed
│   ├── query_logistics running
│   └── query_logistics completed
│
└── 如果创建售后：
    ├── ToolCard 显示 create_after_sales_ticket
    └── 回答里出现 ticket_id
~~~

面试表达：

~~~text
在客服 Agent 里，我不会让模型凭空回答订单和物流问题。
我会把订单、物流、商品、售后这些业务能力包装成可审计的工具。
Agent 只负责判断何时调用工具、如何组合工具结果、如何生成面向用户的话术。
查询类工具低风险，退款和赔付类工具必须走规则引擎或人工审批。
~~~

## 14. RAG 知识库工具从 0 到 1

这一章对应岗位里的：

~~~树形
构建 RAG 检索增强能力
对接商品库、知识库、规则库
优化检索、召回、重排效果
~~~

最重要结论：

~~~树形
RAG 可以先做成工具
工具名：rag_search

后期再升级成：
├── 自动上下文检索
└── MCP RAG Server
~~~

────────────────────────────────────────────────────

### 14.1 客服 RAG 查什么

客服 RAG 不是只查普通文档。

~~~树形
客服知识来源

├── FAQ
│   ├── 怎么退货
│   ├── 怎么改地址
│   ├── 发票怎么开
│   └── 优惠券怎么用
│
├── 售后政策
│   ├── 七天无理由
│   ├── 质量问题退换
│   ├── 运费承担规则
│   └── 超时赔付规则
│
├── 商品知识库
│   ├── 商品规格
│   ├── 使用说明
│   ├── 常见故障
│   └── 适配型号
│
├── 物流规则
│   ├── 发货时效
│   ├── 偏远地区规则
│   ├── 节假日延迟
│   └── 异常件处理流程
│
└── 客服 SOP
    ├── 什么时候安抚
    ├── 什么时候转人工
    ├── 什么时候创建工单
    └── 禁止承诺的话术
~~~

────────────────────────────────────────────────────

### 14.2 RAG 和业务工具的区别

| 类型 | 解决问题 | 示例 |
|------|----------|------|
| 业务工具 | 查实时业务状态 / 执行业务动作 | 查订单、查物流、创建售后 |
| RAG 工具 | 查规则 / 知识 / 说明文档 | 查退货政策、查商品说明 |

例子：

~~~树形
用户："我的耳机坏了，能换吗？"
│
├── query_order
│   └── 查这个订单是否存在、是否已签收、购买时间
│
├── query_product
│   └── 查商品类型、保修期、是否特殊商品
│
├── rag_search_policy
│   └── 查售后政策：质量问题换货规则
│
└── Agent 综合判断后回答
~~~

结论：

~~~树形
业务工具给事实
RAG 给规则
LLM 负责综合事实和规则
~~~

────────────────────────────────────────────────────

### 14.3 rag_search 工具设计

输入：

~~~json
{
  "query": "耳机质量问题可以换货吗",
  "top_k": 5,
  "knowledge_types": ["policy", "faq", "product"]
}
~~~

参数解释：

~~~树形
query
├── 类型：string
└── 含义：用户问题或 Agent 改写后的检索问题

top_k
├── 类型：int
├── 示例：5
└── 含义：最多返回几个知识片段

knowledge_types
├── 类型：list[string]
├── 示例：["policy", "faq"]
└── 含义：限定搜索范围，避免商品问题搜到售后政策外的无关内容
~~~

输出：

~~~json
{
  "ok": true,
  "query": "耳机质量问题可以换货吗",
  "results": [
    {
      "title": "质量问题退换货规则",
      "source": "售后政策库",
      "path": "knowledge/policy/after_sales.md",
      "snippet": "签收后 7 天内，如商品存在质量问题，用户可申请换货或退款。",
      "score": 0.87
    }
  ]
}
~~~

返回给模型的 content 应该简洁：

~~~text
检索到 1 条相关规则：
1.《质量问题退换货规则》：签收后 7 天内，如商品存在质量问题，用户可申请换货或退款。来源：knowledge/policy/after_sales.md
~~~

给 trace / 前端的 data 可以更完整。

────────────────────────────────────────────────────

### 14.4 RAG 内部链路

~~~树形
rag_search(query)
│
├── ① query rewrite（可选）
│   ├── 用户原话："耳机坏了能换吗"
│   └── 改写后："耳机 质量问题 换货 售后政策"
│
├── ② embedding
│   ├── 把 query 转成向量
│   └── 示例：[0.12, -0.03, 0.88, ...]
│
├── ③ vector search
│   ├── 去向量库找相似 chunks
│   └── 返回 top_k 候选
│
├── ④ keyword search（可选）
│   ├── 用关键词补召回
│   └── 适合订单状态名、商品型号、政策编号
│
├── ⑤ rerank
│   ├── 对候选片段重新排序
│   └── 把最相关片段放前面
│
├── ⑥ filter
│   ├── 过滤低分结果
│   ├── 过滤无权限结果
│   └── 过滤过期规则
│
└── ⑦ format result
    ├── title
    ├── snippet
    ├── source
    ├── path
    └── score
~~~

────────────────────────────────────────────────────

### 14.5 文档切片 chunking

错误切法：

~~~树形
整个售后政策.md 作为一个 chunk

问题：
├── 太长
├── 命中不准
├── token 浪费
└── 引用位置不清楚
~~~

更合理切法：

~~~树形
按标题 + 段落切

售后政策.md
├── chunk 1：七天无理由规则
├── chunk 2：质量问题退换规则
├── chunk 3：运费承担规则
├── chunk 4：特殊商品不可退规则
└── chunk 5：超时赔付规则
~~~

一个 chunk 应保留：

~~~json
{
  "id": "policy_after_sales_001",
  "content": "签收后 7 天内，如商品存在质量问题，用户可申请换货或退款。",
  "metadata": {
    "title": "质量问题退换货规则",
    "path": "knowledge/policy/after_sales.md",
    "knowledge_type": "policy",
    "line_start": 10,
    "line_end": 18,
    "updated_at": "2026-06-01",
    "enabled": true
  }
}
~~~

chunk 原则：

~~~树形
一个 chunk 只讲一个规则点
保留来源
保留标题
保留更新时间
不要太短
不要太长
可独立被模型理解
~~~

────────────────────────────────────────────────────

### 14.6 RAG 召回与重排

召回：

~~~树形
召回 = 先把可能相关的内容找出来

目标：
宁可多找一些候选
不要漏掉关键规则
~~~

重排：

~~~树形
重排 = 从候选里重新选最相关的

目标：
把真正有用的结果排在前面
减少无关内容进入 prompt
~~~

常见组合：

~~~树形
Hybrid Search
├── vector search 负责语义相似
├── keyword search 负责精确词
└── reranker 负责最终排序
~~~

例子：

~~~树形
用户："iPhone15 手机壳能退吗？"

只用向量：
├── 可能搜到手机售后
└── 不一定命中 iPhone15 手机壳这个商品

加关键词：
├── iPhone15
├── 手机壳
└── 退货

重排后：
└── 最相关结果：配件类商品退货规则
~~~

────────────────────────────────────────────────────

### 14.7 RAG 接入本项目

推荐最小文件边界：

~~~树形
agent_prototype/rag/
├── types.py
│   ├── DocumentChunk
│   ├── SearchResult
│   └── RAGSearchRequest
│
├── loader.py
│   └── 从 docs / knowledge / specs 读取文档
│
├── chunker.py
│   └── 文档切片
│
├── embeddings.py
│   └── 调 embedding 模型
│
├── store.py
│   └── 保存向量和检索
│
└── service.py
    ├── index_workspace()
    └── search(query, top_k)

agent_prototype/tools/builtin/rag_search.py
└── 把 RAGService.search 包成工具
~~~

进入运行链路：

~~~树形
AgentRunner
└── ToolRegistry
    └── rag_search
        └── RAGService.search()
            ├── embedding
            ├── vector store
            ├── rerank
            └── SearchResult[]
~~~

前端视觉映射：

~~~树形
ToolCard: rag_search
├── query: "耳机质量问题换货规则"
├── top_k: 5
├── 命中 3 条
├── 最高 score: 0.87
└── 展开后显示来源 path / title / snippet
~~~

面试表达：

~~~text
我会把 RAG 先做成一个可追踪的工具 rag_search，而不是一开始就隐式塞进 prompt。
这样每次检索的 query、top_k、命中文档、score 都能进入 trace，方便评估召回质量。
当本地 RAG 稳定后，再把它包装成 MCP server，让多个 Agent 复用同一个知识检索能力。
~~~

## 15. Agent Eval — 怎么判断 Agent 好不好

这一章对应岗位里的：

~~~树形
Agent 评估体系
效果评估
成本监控
延迟优化
异常告警
问题复盘
~~~

最重要结论：

~~~树形
没有 Eval，就不知道 Agent 是变好了还是变差了
~~~

────────────────────────────────────────────────────

### 15.1 为什么 Agent Eval 比普通模型评测更复杂

普通 LLM 评测：

~~~树形
输入问题
└── 输出答案

评估：
├── 答案是否正确
└── 语言是否清楚
~~~

Agent 评测：

~~~树形
输入问题
│
├── 是否选对工具
├── 工具参数是否正确
├── 是否正确处理工具错误
├── 是否正确使用 RAG
├── 是否遵守业务规则
├── 是否需要转人工
├── 成本是否合理
├── 延迟是否合理
└── 最终答案是否正确
~~~

所以 Agent Eval 评的不只是答案，而是整条执行链路。

────────────────────────────────────────────────────

### 15.2 客服 Agent 评测集

一条评测样本：

~~~json
{
  "id": "case_001",
  "user_input": "我的订单 O202606150001 什么时候到？",
  "expected_tools": ["query_order", "query_logistics"],
  "expected_answer_points": [
    "说明订单已发货",
    "说明当前物流状态",
    "说明预计送达时间"
  ],
  "should_transfer_to_human": false,
  "risk_level": "low"
}
~~~

评测集分类：

~~~树形
客服 Eval Dataset

├── 订单类
│   ├── 查订单状态
│   ├── 查支付状态
│   └── 查是否发货
│
├── 物流类
│   ├── 查物流轨迹
│   ├── 物流延迟
│   ├── 地址异常
│   └── 疑似丢件
│
├── 售后类
│   ├── 退货
│   ├── 换货
│   ├── 维修
│   └── 赔付
│
├── 商品类
│   ├── 商品规格
│   ├── 库存
│   ├── 保修
│   └── 使用说明
│
├── 规则类
│   ├── 七天无理由
│   ├── 运费规则
│   └── 特殊商品限制
│
└── 安全类
    ├── 越权查订单
    ├── 要求泄露隐私
    ├── 要求违规退款
    └── 情绪激烈需转人工
~~~

────────────────────────────────────────────────────

### 15.3 核心指标

| 指标 | 含义 | 例子 |
|------|------|------|
| Tool Accuracy | 工具选择是否正确 | 该查物流时是否调用 query_logistics |
| Argument Accuracy | 工具参数是否正确 | order_id 是否填对 |
| RAG Recall | 是否检索到正确知识 | 退货问题是否命中退货政策 |
| Answer Correctness | 最终答案是否正确 | 是否说清楚预计送达时间 |
| Policy Compliance | 是否遵守业务规则 | 不乱承诺赔付 |
| Handoff Accuracy | 是否正确转人工 | 高风险问题是否转人工 |
| Latency | 响应耗时 | 总耗时 3.2s |
| Cost | token / API 成本 | 本轮花费 0.01 元 |
| Recovery Rate | 失败恢复率 | 工具超时后是否给出合理兜底 |

指标拆解：

~~~树形
一次 Agent Run
├── tool_call_correct: true / false
├── tool_args_correct: true / false
├── rag_hit_expected_doc: true / false
├── final_answer_score: 0-5
├── policy_violation: true / false
├── should_handoff: true / false
├── actually_handoff: true / false
├── latency_ms: 3200
├── input_tokens: 3000
├── output_tokens: 500
└── total_cost: 0.01
~~~

────────────────────────────────────────────────────

### 15.4 自动评测流程

~~~树形
Eval Runner
│
├── ① 读取 eval cases
│   └── cases/customer_service.jsonl
│
├── ② 对每条 case 启动一次 Agent run
│   └── user_input → RunService
│
├── ③ 收集 trace
│   ├── assistant_tool_call
│   ├── tool_result
│   ├── final_answer
│   ├── usage
│   └── latency
│
├── ④ 规则评分
│   ├── expected_tools 是否出现
│   ├── 工具参数是否匹配
│   ├── 是否转人工
│   └── 是否出现禁用话术
│
├── ⑤ LLM-as-Judge 评分（可选）
│   ├── 答案是否完整
│   ├── 语气是否合适
│   └── 是否违反政策
│
└── ⑥ 输出报告
    ├── pass_rate
    ├── tool_accuracy
    ├── rag_recall
    ├── avg_latency
    ├── avg_cost
    └── failed_cases
~~~

────────────────────────────────────────────────────

### 15.5 失败案例复盘

失败案例不要只看最终答案，要看 trace。

~~~树形
用户："我的订单还没到，能赔吗？"
│
├── 期望：
│   ├── query_order
│   ├── query_logistics
│   ├── rag_search_policy
│   └── 不直接承诺赔付
│
├── 实际：
│   ├── query_order
│   └── final_answer: "可以赔付"
│
└── 失败原因：
    ├── 漏调 query_logistics
    ├── 漏调 rag_search_policy
    └── 违反赔付规则
~~~

修复方向：

~~~树形
可能修 prompt
├── 明确赔付前必须查物流和政策
│
可能修工具描述
├── check_refund_policy 描述不够清楚
│
可能修 RAG
├── 赔付规则没有被召回
│
可能修流程
└── 高风险赔付必须审批
~~~

面试表达：

~~~text
我不会只看最终回答是否像人话，而会把 Agent run 拆成工具选择、参数、RAG 命中、规则遵守、成本和延迟几个维度评估。
客服场景里尤其要评估是否误承诺赔付、是否越权查单、是否该转人工而没有转。
所有失败样本都应该回看 trace，定位是 prompt、工具描述、RAG 召回还是业务规则的问题。
~~~

## 16. Agent 成本与延迟

这一章对应岗位里的：

~~~树形
成本结构
延迟瓶颈
成本监控
延迟优化
高并发 SaaS 服务经验
~~~

最重要结论：

~~~树形
Agent 慢，不一定是模型慢
Agent 贵，不一定是输出贵
要拆开看每一层
~~~

────────────────────────────────────────────────────

### 16.1 一次 Agent Run 的成本来自哪里

~~~树形
总成本
├── LLM 输入 token 成本
│   ├── system_prompt
│   ├── history messages
│   ├── tool definitions
│   ├── RAG context
│   └── tool results
│
├── LLM 输出 token 成本
│   ├── 普通回答
│   ├── thinking / reasoning
│   └── tool_calls
│
├── embedding 成本
│   ├── query embedding
│   └── document indexing embedding
│
├── rerank 成本
│   └── reranker API / 本地模型
│
├── 工具 API 成本
│   ├── 订单系统
│   ├── 物流系统
│   └── 第三方接口
│
└── 基础设施成本
    ├── 数据库
    ├── 向量库
    ├── 队列
    └── 服务实例
~~~

一次 run 应记录：

~~~json
{
  "run_id": "run_001",
  "input_tokens": 3200,
  "output_tokens": 600,
  "model_latency_ms": 1800,
  "tool_latency_ms": 900,
  "rag_latency_ms": 300,
  "total_latency_ms": 3200,
  "retry_count": 0,
  "estimated_cost": 0.012
}
~~~

────────────────────────────────────────────────────

### 16.2 延迟来自哪里

~~~树形
总延迟
├── 模型首 token 延迟
├── 模型完整输出延迟
├── 工具执行延迟
├── 多轮 LLM 调用延迟
├── RAG 检索延迟
├── rerank 延迟
├── 数据库读写延迟
├── 流式传输延迟
└── 前端渲染延迟
~~~

客服 Agent 常见慢链路：

~~~树形
用户问："我这个订单能不能退？"
│
├── 第 1 次 LLM：判断要查订单
├── query_order：查订单
├── 第 2 次 LLM：判断要查政策
├── rag_search_policy：查规则
├── 第 3 次 LLM：生成回答
└── 总共 3 次模型调用 + 2 次工具调用
~~~

优化方向：

~~~树形
减少模型轮次
├── prompt 教模型一次性调用 query_order + rag_search_policy
│
并发工具调用
├── query_order 和 query_logistics 可并发
│
控制上下文
├── compact 历史
├── 限制 RAG top_k
└── 裁剪 tool result
│
缓存
├── 用户短时间重复查同一订单
├── 商品知识
└── FAQ 检索结果
│
流式输出
└── 先给用户展示正在查询状态，降低等待感
~~~

────────────────────────────────────────────────────

### 16.3 本项目已有基础

~~~树形
已有能力
├── stream 输出
│   └── 用户能看到实时增量
│
├── tool run_event
│   └── 工具开始、成功、失败能进入 Trace
│
├── RunEvent / Trace
│   └── 能记录工具调用过程
│
├── usage
│   └── 可记录 token 使用
│
├── compact
│   └── 控制历史上下文长度
│
├── 并发工具执行
│   └── 多个 ready tools 可并发跑
│
└── resume / approval
    └── 暂停后可恢复，不用整轮重跑
~~~

还应补：

~~~树形
LatencyMetrics
├── model_start_ms
├── first_token_ms
├── model_done_ms
├── tool_start_ms
├── tool_done_ms
├── rag_start_ms
├── rag_done_ms
└── total_ms

CostMetrics
├── input_tokens
├── output_tokens
├── embedding_tokens
├── rerank_count
├── model_cost
├── embedding_cost
└── total_cost
~~~

────────────────────────────────────────────────────

### 16.4 成本优化原则

~~~树形
减少无效输入
├── system prompt 不要无限膨胀
├── tools 不要全量暴露
├── RAG 不要塞太多 chunks
└── tool result 要摘要化

减少无效输出
├── 客服回答要短
├── 不输出无关解释
└── thinking 不给用户展示

减少无效调用
├── 能本地规则判断就不用 LLM
├── 能缓存就不重复查
├── 能并发就不要串行
└── 高风险动作先规则预判
~~~

面试表达：

~~~text
我会把一次 Agent run 的成本拆成模型输入、模型输出、RAG、rerank、工具 API 和基础设施几部分。
延迟上会区分首 token、模型总耗时、工具耗时、RAG 耗时和数据库耗时。
优化时不会只换更快模型，而是先看 trace，判断瓶颈是上下文太长、工具串行、RAG top_k 过大，还是多轮模型调用太多。
~~~

## 17. MCP 最小接入闭环

这一章对应岗位里的：

~~~树形
了解 MCP
Agent 互操作协议
相关实践经验
工具与接口开发
~~~

最重要结论：

~~~树形
MCP 不替代 ToolRegistry
MCP tool 应该映射进 ToolRegistry
让 Agent 像调用本地工具一样调用 MCP 工具
~~~

────────────────────────────────────────────────────

### 17.1 MCP 最小闭环是什么

~~~树形
最小闭环

① 配置 server
│
├── server_id
├── command / args
├── url
├── env
└── enabled_tools
│
② 连接 server
│
├── stdio
└── streamable http
│
③ 发现 tools
│
├── list_tools
├── name
├── description
└── input_schema
│
④ 注册到 ToolRegistry
│
├── 本地工具
└── MCP 工具 wrapper
│
⑤ 执行 call_tool
│
├── Agent 生成 tool_call
├── ToolRegistry 找到 MCP wrapper
├── MCP client 调 server
└── 返回 ToolResult
│
⑥ 进入 trace
└── 前端显示 MCP tool 执行过程
~~~

────────────────────────────────────────────────────

### 17.2 MCP server 配置

示例配置：

~~~json
{
  "mcp_servers": {
    "customer_knowledge": {
      "enabled": true,
      "transport": "stdio",
      "command": "python3",
      "args": ["-m", "agent_prototype.rag.mcp_server"],
      "cwd": "/Users/wangxu/Documents/AGENT Build",
      "env": {
        "RAG_INDEX_PATH": ".rag/index"
      },
      "startup_timeout_sec": 10,
      "tool_timeout_sec": 30,
      "enabled_tools": ["search_policy", "search_product_faq"],
      "disabled_tools": []
    }
  }
}
~~~

字段解释：

~~~树形
server_id: customer_knowledge
├── 含义：本项目内部识别这个 MCP server 的名字

enabled
├── true  → 启用
└── false → 不启用

transport
├── stdio → 本地进程通信
└── http  → 远程服务通信

command / args
├── stdio 模式使用
└── 含义：怎么启动 server

url
├── http 模式使用
└── 含义：远程 MCP server 地址

startup_timeout_sec
└── 含义：server 启动最多等多久

tool_timeout_sec
└── 含义：一次工具调用最多等多久

enabled_tools
└── 只允许暴露这些工具

disabled_tools
└── 禁止暴露这些工具
~~~

────────────────────────────────────────────────────

### 17.3 DiscoveredMCPTool

MCP server 暴露出来的工具，不要直接等同于本地 ToolDefinition。

中间应有一个 discovered tool 对象：

~~~树形
DiscoveredMCPTool
├── server_id
│   └── 示例："customer_knowledge"
├── name
│   └── 示例："search_policy"
├── runtime_name
│   └── 示例："mcp.customer_knowledge.search_policy"
├── description
│   └── 给模型看的工具说明
├── input_schema
│   └── JSON Schema 参数定义
└── timeout_sec
    └── 工具调用超时
~~~

为什么要有 runtime_name：

~~~树形
不同 server 可能都有 search
├── github.search
├── browser.search
└── knowledge.search

如果都叫 search：
├── 名字冲突
├── trace 不清楚来源
└── Agent 难区分

所以 runtime_name 应带 server 信息
~~~

────────────────────────────────────────────────────

### 17.4 MCPToolBridge

MCPToolBridge 的职责：

~~~树形
MCPToolBridge
├── 负责：
│   ├── 把 MCP tool 包成 ToolRegistry 可执行工具
│   ├── 接收 arguments
│   ├── 调 MCPClient.call_tool()
│   ├── 处理 timeout
│   ├── 处理 MCP error
│   └── 转成统一 ToolResult
│
└── 不负责：
    ├── 决定 Agent 是否要调用
    ├── 做业务规则判断
    ├── 直接写前端状态
    └── 绕过 trace / approval
~~~

调用链：

~~~树形
Agent tool_call
│
├── name = "mcp.customer_knowledge.search_policy"
├── arguments = {"query":"七天无理由退货"}
│
└── ToolRegistry.execute_tool_call()
    │
    └── MCPToolBridge.execute()
        │
        └── MCPClient.call_tool(
              server_id="customer_knowledge",
              tool_name="search_policy",
              arguments={"query":"七天无理由退货"}
            )
            │
            └── MCP Server 执行 search_policy
                │
                └── 返回 MCP tool result
                    │
                    └── 转成 ToolResult
~~~

统一返回：

~~~json
{
  "ok": true,
  "content": "找到 2 条售后政策...",
  "metadata": {
    "source": "mcp",
    "server_id": "customer_knowledge",
    "tool_name": "search_policy"
  }
}
~~~

────────────────────────────────────────────────────

### 17.5 MCP 错误处理

常见错误：

~~~树形
MCP_SERVER_DISABLED
├── server 未启用

MCP_SERVER_START_TIMEOUT
├── stdio server 启动超时

MCP_TOOL_NOT_FOUND
├── server 没有这个 tool

MCP_TOOL_TIMEOUT
├── tool 调用超时

MCP_AUTH_FAILED
├── 鉴权失败

MCP_PROTOCOL_ERROR
├── server 返回不符合协议

MCP_INTERNAL_ERROR
└── server 内部异常
~~~

进入统一错误：

~~~树形
MCP error
└── ToolResult(ok=False)
    ├── content: 给模型看的错误摘要
    ├── error_code
    └── metadata.source = "mcp"
~~~

前端显示：

~~~树形
ToolCard
├── name: mcp.customer_knowledge.search_policy
├── state: failed
├── error_code: MCP_TOOL_TIMEOUT
└── message: 知识库检索超时
~~~

面试表达：

~~~text
我会把 MCP 接入做在工具平台层，而不是把 MCP server 直接塞进 Agent 定义。
server 配置、tool discovery、tool bridge、runtime tool surface 是四个层级。
MCP tool 调用最终必须转成统一 ToolResult，并继续进入现有 trace、审批和错误处理链路。
~~~

## 18. 面试高频问题与回答框架

这一章不是背答案，而是训练表达结构。

回答任何 Agent 问题，尽量按这个顺序：

~~~树形
① 先说结论
② 再说链路
③ 再说项目实现
④ 最后说风险和优化
~~~

────────────────────────────────────────────────────

### 18.1 你这个 Agent 系统怎么设计？

回答框架：

~~~text
我的项目核心是一个可追踪的 Agent runtime。
主链路是：用户输入进入 RunService，RunContextFactory 组装 session、模型、agent、workspace、权限和上下文；AgentRunner 调模型并处理 tool_calls；ToolRegistry 执行本地工具或外部工具；RunLifecycle 把文本、工具事件、审批、错误和终态统一成事件流；RunRecorder 负责落库和状态持久化。

这个设计的重点不是只调一次模型，而是让一次 Agent run 可以被追踪、暂停、恢复、审批和复盘。
~~~

关键词：

~~~树形
RunService
RunContextFactory
AgentRunner
ToolRegistry
RunLifecycle
RunRecorder
Trace
Approval
Resume
~~~

────────────────────────────────────────────────────

### 18.2 tool calling 怎么跑？

回答框架：

~~~text
模型不会直接执行工具，它只生成 tool_calls。
Runtime 收到 tool_calls 后，先做工具白名单校验、参数解析、风险判断和审批判断。
允许执行的工具进入 ToolRegistry，由本地 handler 或 MCP bridge 执行。
工具结果会变成 role=tool 的消息追加回对话状态，然后 AgentRunner 继续下一轮模型调用，直到模型给出 final answer。
~~~

链路：

~~~树形
LLM
└── assistant.tool_calls
    └── ToolRunner
        ├── allowlist check
        ├── approval check
        ├── middleware
        └── ToolRegistry.execute_tool_call()
            └── ToolResult
                └── ChatMessage(role="tool")
                    └── 下一轮 LLM
~~~

────────────────────────────────────────────────────

### 18.3 RAG 怎么做召回和重排？

回答框架：

~~~text
我会先把知识库按标题和语义段落切成 chunk，并保留 path、title、line、knowledge_type 等 metadata。
查询时先做 query rewrite，再用 embedding 做向量召回，必要时结合关键词召回，最后用 reranker 对候选结果重排。
RAG 工具返回的不只是文本，还包括来源、score 和 metadata，这样 trace 能评估命中了哪些知识。
~~~

可补充：

~~~树形
优化方向
├── 调整 chunk 粒度
├── hybrid search
├── rerank
├── top_k 控制
├── score threshold
├── 过期文档过滤
└── 按知识类型过滤
~~~

────────────────────────────────────────────────────

### 18.4 客服订单工具怎么接？

回答框架：

~~~text
订单、物流、售后这些不是模型知识，而是业务系统能力。
我会把它们包装成结构化工具，比如 query_order、query_logistics、create_after_sales_ticket。
查询类工具通常低风险，可以直接调用；退款、赔付、取消订单这类高风险工具必须走规则引擎或人工审批。
工具输入输出都要结构化，结果进入 trace，方便审计和复盘。
~~~

链路：

~~~树形
用户问题
└── Agent 判断意图
    ├── query_order
    ├── query_logistics
    ├── rag_search_policy
    └── create_after_sales_ticket / transfer_to_human
~~~

────────────────────────────────────────────────────

### 18.5 工具失败怎么恢复？

回答框架：

~~~text
工具失败要区分类型：参数错误、权限错误、业务不存在、超时、外部系统异常。
失败后不会直接崩掉整个 run，而是转成统一 ToolResult(ok=false) 和 tool_error event。
模型可以基于错误继续回复用户，比如要求补充订单号、稍后重试或转人工。
如果是审批暂停，系统保存 saved_messages 和 event_index，用户批准后从断点 resume，不需要整轮重跑。
~~~

分类：

~~~树形
失败类型
├── USER_INPUT_MISSING       → 让用户补信息
├── ACCESS_DENIED            → 拒绝泄露
├── BUSINESS_NOT_FOUND       → 提醒核对
├── TOOL_TIMEOUT             → 重试 / 转人工
├── EXTERNAL_API_ERROR       → 兜底话术
└── APPROVAL_REQUIRED        → 暂停等待用户
~~~

────────────────────────────────────────────────────

### 18.6 多 Agent 怎么协作？

回答框架：

~~~text
我会先区分内部子 Agent 和标准 A2A。
当前项目里可以通过 spawn_child_agent 启动内部子 Agent，把复杂任务拆给 reviewer、researcher、coder 等角色。
A2A 更适合跨系统、跨框架的 Agent 协作，它需要 Agent Card、Task、Artifact 和状态同步。
我的设计会先把内部 child run 生命周期和 trace 做稳定，再考虑把本项目 Agent 暴露成 A2A server。
~~~

区别：

~~~树形
内部 child agent
├── 同一个系统内
├── 共享数据库 / trace
└── 实现成本低

A2A
├── 跨系统
├── 标准协议
├── Agent Card
├── Task lifecycle
└── Artifact
~~~

────────────────────────────────────────────────────

### 18.7 MCP 和普通工具有什么区别？

回答框架：

~~~text
普通工具通常是项目内注册的 Python handler。
MCP 是一个标准协议，用来连接外部工具和数据源。
在我的架构里，MCP 不会替代 ToolRegistry，而是通过 discovery 找到外部 server 暴露的 tools，再用 MCPToolBridge 包装成 ToolRegistry 可执行工具。
这样本地工具和 MCP 工具可以共用审批、trace、错误处理和前端展示。
~~~

链路：

~~~树形
普通工具：
ToolRegistry → Python handler

MCP 工具：
ToolRegistry → MCPToolBridge → MCPClient → MCPServer
~~~

────────────────────────────────────────────────────

### 18.8 怎么评估 Agent 效果？

回答框架：

~~~text
我会建立客服场景 eval dataset，每条样本包含用户问题、期望工具、期望参数、期望答案要点、是否应该转人工和风险等级。
评估时不只看最终答案，还看工具选择准确率、参数准确率、RAG 命中率、规则遵守率、人工转接准确率、平均延迟和平均成本。
失败样本会回看 trace，定位问题来自 prompt、工具描述、RAG 召回、业务规则还是模型本身。
~~~

指标：

~~~树形
Eval Metrics
├── tool_accuracy
├── argument_accuracy
├── rag_recall
├── answer_correctness
├── policy_compliance
├── handoff_accuracy
├── avg_latency
├── avg_cost
└── recovery_rate
~~~

────────────────────────────────────────────────────

### 18.9 怎么优化成本和延迟？

回答框架：

~~~text
我会先通过 trace 把一次 run 的耗时拆开：模型首 token、模型总耗时、工具耗时、RAG 耗时、rerank 耗时、数据库耗时和前端流式耗时。
成本也拆成输入 token、输出 token、embedding、rerank 和工具 API 成本。
优化上优先减少无效上下文、控制 RAG top_k、裁剪 tool result、并发执行独立工具、缓存稳定知识和订单短期查询结果。
~~~

优化手段：

~~~树形
成本优化
├── compact 历史
├── 精简 system prompt
├── 工具按需暴露
├── RAG top_k 控制
└── tool result 摘要化

延迟优化
├── stream
├── 并发工具
├── 缓存
├── 减少模型轮次
└── 慢工具异步进度
~~~

────────────────────────────────────────────────────

### 18.10 这份 JD 的项目包装话术

可以这样介绍你的项目：

~~~text
我做的是一个面向 AI Agent 的执行引擎原型，重点解决多轮对话、工具调用、上下文组装、审批暂停、恢复执行、状态持久化和 trace 可观测问题。

如果落到客服场景，我会把订单、物流、商品、售后包装成业务工具，把 FAQ、商品说明和售后规则做成 RAG 检索工具，再统一接入 ToolRegistry。
Agent 负责根据用户问题规划调用哪些工具，工具结果和 RAG 结果都会进入 trace，最后由模型生成用户可读回答。

后续扩展上，本地工具可以通过 MCP 标准化接入，内部子 Agent 可以逐步演进到 A2A 协议，实现跨系统多 Agent 协作。
~~~

注意不要这样说：

~~~text
我了解 MCP、A2A、RAG。
~~~

太空。应该说：

~~~text
我在项目里会把 MCP 放在工具平台层，把 RAG 先做成可追踪工具，把 A2A 放在多 Agent 协作层。
MCP tool 和本地 tool 最终都进入统一 ToolRegistry，复用审批、trace 和错误处理。
~~~

## 19. Agent 记忆 — 基础概念与项目接入

这一章对应岗位里的：

~~~树形
上下文工程
记忆与状态管理
多轮交互
用户画像
长期任务连续性
~~~

先记住一句话：

~~~树形
Agent 记忆不是一个东西
Agent 记忆 = 当前上下文 + 会话状态 + 摘要记忆 + 长期记忆 + 用户画像 + 工具执行轨迹
~~~

────────────────────────────────────────────────────

### 19.1 为什么 Agent 需要记忆

没有记忆：

~~~树形
第 1 轮：
用户："我买的耳机坏了。"
Agent："请提供订单号。"

第 2 轮：
用户："订单号是 O1001。"
Agent 不记得上一轮
└── 不知道用户说的是耳机坏了
~~~

有记忆：

~~~树形
第 1 轮：
用户："我买的耳机坏了。"
Agent 记录：
├── 用户商品：耳机
├── 问题：坏了
└── 可能意图：售后

第 2 轮：
用户："订单号是 O1001。"
Agent 结合上一轮：
├── query_order(O1001)
├── rag_search("耳机质量问题售后规则")
└── 给出换货 / 维修 / 转人工建议
~~~

结论：

~~~树形
记忆解决：
├── 多轮连续理解
├── 长任务不中断
├── 用户偏好复用
├── 历史决策复盘
└── 减少重复询问
~~~

────────────────────────────────────────────────────

### 19.2 Agent 记忆分类

~~~树形
Agent Memory

├── Working Memory（工作记忆）
│   ├── 含义：当前这一轮模型能看到的上下文
│   ├── 生命周期：一次 LLM 请求内
│   └── 示例：system prompt + 最近 messages + tool results
│
├── Short-term Memory（短期记忆）
│   ├── 含义：当前 session 的对话历史
│   ├── 生命周期：一个会话内
│   └── 示例：用户刚才说的问题、模型刚才调用的工具
│
├── Long-term Memory（长期记忆）
│   ├── 含义：跨 session 保存的稳定信息
│   ├── 生命周期：多次会话
│   └── 示例：用户偏好、常用项目、长期目标
│
├── Semantic Memory（语义记忆）
│   ├── 含义：知识性记忆
│   └── 示例：项目规则、客服政策、商品知识
│
├── Episodic Memory（事件记忆）
│   ├── 含义：发生过什么事
│   └── 示例：某次 run 调用了哪些工具、失败在哪一步
│
├── Procedural Memory（过程记忆）
│   ├── 含义：怎么做某类任务
│   └── 示例：售后处理 SOP、代码 review 流程
│
└── User Profile Memory（用户画像记忆）
    ├── 含义：用户稳定偏好 / 背景
    └── 示例：用户喜欢中文解释、正在学习 Python、目标是 AI Agent 面试
~~~

容易混淆：

| 名称 | 重点 | 项目里怎么体现 |
|------|------|----------------|
| context | 本轮模型能看到什么 | ContextAssembler / messages |
| state | 当前会话状态是什么 | RunState |
| memory | 可复用历史信息 | SessionStore / future MemoryStore |
| trace | 执行过程发生了什么 | RunTraceStore / ToolTracer |
| RAG | 外部知识怎么查 | rag_search / vector store |

────────────────────────────────────────────────────

### 19.3 当前项目已有的记忆能力

当前项目不是完全没有 memory，已经有几类基础能力。

~~~树形
已有记忆能力

├── RunState
│   ├── 保存 messages
│   ├── 保存 step
│   └── 是当前会话短期记忆的核心对象
│
├── SessionStore
│   ├── 读取 session state
│   ├── 保存 session state
│   └── 让多轮对话能延续
│
├── CompactService
│   ├── 判断上下文是否太长
│   ├── 调 HistoryCompactor 生成摘要
│   └── 用摘要替代中段历史
│
├── HistoryCompactor
│   ├── 把旧消息压缩成 summary
│   └── 降低 token 成本
│
├── ContextAssembler
│   ├── 读取 AGENTS.md
│   ├── 读取 workspace context
│   ├── 注入 skill catalog
│   └── 拼成运行时上下文
│
├── RunTraceStore
│   ├── 保存每次 run
│   ├── 保存 RunEvent
│   └── 是 episodic memory 的雏形
│
├── ToolTracer
│   ├── 记录工具开始
│   ├── 记录工具结束
│   └── 记录审批请求
│
└── WorkspaceService
    ├── 保存工作区绑定
    └── 让 session 知道当前项目目录
~~~

当前链路：

~~~树形
用户发起 run
│
├── RunContextFactory.assemble()
│   ├── SessionStore.get(session_id)
│   │   └── 读取 RunState(messages, step)
│   │
│   ├── 如果上下文过长：
│   │   └── CompactService.auto_compact_in_memory()
│   │       └── HistoryCompactor.compact()
│   │
│   └── ContextAssembler.assemble()
│       └── 组装 AGENTS.md / skill / workspace context
│
├── AgentRunner 运行
│   └── 不断追加 user / assistant / tool messages
│
└── RunRecorder.finalize_run()
    ├── 保存最终 RunState
    ├── 保存 run trace
    └── 保存 tool events
~~~

结论：

~~~树形
当前项目已有：
├── 短期会话记忆
├── 压缩摘要记忆
├── 执行轨迹记忆
└── 工作区上下文记忆

当前项目还缺：
├── 跨 session 长期记忆
├── 用户画像记忆
├── 可检索 memory store
├── memory 写入策略
├── memory 删除 / 隐私策略
└── memory 评估体系
~~~

────────────────────────────────────────────────────

### 19.4 长期记忆应该怎么接入

不要一开始把所有对话都塞进长期记忆。

合理链路：

~~~树形
一次 run 完成后
│
├── MemoryExtractor
│   ├── 从 user / assistant / tool events 中提取候选记忆
│   ├── 判断哪些信息值得长期保存
│   └── 输出 MemoryCandidate[]
│
├── MemoryPolicy
│   ├── 判断是否允许保存
│   ├── 判断是否需要用户确认
│   ├── 去重
│   └── 合并旧记忆
│
├── MemoryStore
│   ├── 保存长期记忆
│   ├── 保存 metadata
│   └── 支持搜索
│
└── 下一次 run 前
    ├── MemoryRetriever.search(user_input)
    ├── 找到相关长期记忆
    └── 注入 ContextAssembler
~~~

推荐新增边界：

~~~树形
agent_prototype/memory/long_term/
├── types.py
│   ├── MemoryRecord
│   ├── MemoryCandidate
│   └── MemorySearchResult
│
├── extractor.py
│   └── 从 run 后内容提取候选记忆
│
├── policy.py
│   └── 判断是否保存、是否合并、是否需要确认
│
├── store.py
│   └── SQLite / vector store 持久化
│
├── retriever.py
│   └── 根据当前问题检索相关记忆
│
└── service.py
    ├── write_from_run()
    └── retrieve_for_run()
~~~

MemoryRecord 示例：

~~~json
{
  "id": "mem_001",
  "scope": "user",
  "memory_type": "preference",
  "content": "用户正在学习 Python 和 AI Agent 项目，目标是准备 AI Agent 工程岗位面试。",
  "confidence": 0.9,
  "source_session_id": "session_001",
  "source_run_id": "run_001",
  "created_at": "2026-06-15 20:00:00",
  "updated_at": "2026-06-15 20:00:00"
}
~~~

字段解释：

~~~树形
scope
├── user       → 用户级记忆
├── workspace  → 工作区级记忆
└── agent      → agent 级记忆

memory_type
├── preference → 偏好
├── fact       → 事实
├── goal       → 长期目标
├── workflow   → 做事流程
└── constraint → 限制 / 禁忌

confidence
├── 0.0-1.0
└── 表示这条记忆可信度

source_session_id / source_run_id
└── 可追溯来源，方便复盘和删除
~~~

────────────────────────────────────────────────────

### 19.5 记忆写入策略

不能什么都记。

应该保存：

~~~树形
值得长期保存
├── 用户明确偏好
│   └── "以后都用中文解释"
│
├── 长期目标
│   └── "我要准备 AI Agent 工程岗位"
│
├── 稳定项目事实
│   └── "当前项目使用 FastAPI + Vue 3"
│
├── 反复出现的约束
│   └── "后端 Python 非明确指令不要直接改"
│
└── 复用流程
    └── "文档笔记按树形格式写"
~~~

不应该保存：

~~~树形
不该长期保存
├── 临时闲聊
├── 一次性命令
├── 密码 / token / 私密信息
├── 未确认的猜测
├── 过期业务状态
└── 工具返回的大量原始数据
~~~

写入流程：

~~~树形
run completed
│
├── MemoryExtractor 提取候选
│
├── MemoryPolicy 判断
│   ├── 明确偏好 → 可自动保存
│   ├── 敏感信息 → 不保存
│   ├── 不确定事实 → 降低 confidence
│   └── 重要长期记忆 → 可请求用户确认
│
├── 去重 / 合并
│   ├── 已有相同记忆 → update
│   └── 新信息 → insert
│
└── MemoryStore 持久化
~~~

────────────────────────────────────────────────────

### 19.6 记忆检索与注入

长期记忆不是全量塞进 prompt。

正确方式：

~~~树形
用户新问题
│
├── MemoryRetriever.search(user_input)
│   ├── 按 user_id / workspace_id 过滤
│   ├── 语义检索相关记忆
│   ├── 按 memory_type 过滤
│   └── 返回 top_k
│
├── ContextAssembler
│   ├── AGENTS.md
│   ├── skill catalog
│   ├── session messages
│   ├── compact summary
│   └── relevant memories
│
└── LLM
    └── 基于相关记忆回答
~~~

注入格式：

~~~text
以下是和当前用户相关的长期记忆，只作为上下文参考，不要逐字复述：
1. 用户正在学习 Python 和 AI Agent 项目，目标是准备 AI Agent 工程岗位面试。
2. 用户偏好结构化中文解释，避免过分夸赞。
3. 当前项目后端 Python 默认走 Coach Mode，非明确命令不要直接改。
~~~

为什么要写“不要逐字复述”：

~~~树形
避免模型每次回答都说：
"我记得你正在学习..."

记忆应该辅助判断
不应该污染最终回答
~~~

────────────────────────────────────────────────────

### 19.7 记忆和 RAG 的区别

| 对比项 | Memory | RAG |
|--------|--------|-----|
| 存什么 | 用户 / 会话 / 项目中形成的经验和偏好 | 外部知识库、规则、文档 |
| 来源 | 对话、工具执行、用户确认 | 文档、FAQ、商品库、政策库 |
| 更新频率 | 随交互持续更新 | 按知识库更新 |
| 典型问题 | 用户喜欢什么、之前做过什么 | 规则是什么、文档怎么说 |
| 接入点 | ContextAssembler / MemoryRetriever | rag_search / RAGService |

例子：

~~~树形
Memory：
└── "用户准备 AI Agent 工程岗位面试"

RAG：
└── "售后政策规定签收 7 天内质量问题可换货"
~~~

结论：

~~~树形
Memory 记用户和过程
RAG 查知识和规则
两者都可以通过 ContextAssembler 注入
也都可以做成工具查询
~~~

────────────────────────────────────────────────────

### 19.8 面试表达

~~~text
我的项目里已经有短期会话记忆和执行轨迹记忆：RunState 保存 messages，SessionStore 持久化会话状态，CompactService 和 HistoryCompactor 负责把长历史压缩成摘要，RunTraceStore 和 ToolTracer 保存每次工具调用和事件。

如果继续扩展长期记忆，我会新增 MemoryExtractor、MemoryPolicy、MemoryStore 和 MemoryRetriever。
run 完成后从对话和 trace 中提取候选记忆，经过隐私、去重、置信度和用户确认策略后写入长期记忆库。
下一次 run 前只检索和当前问题相关的记忆，通过 ContextAssembler 注入，而不是把所有历史都塞进 prompt。
~~~

## 20. Agent Harness — 思想与本项目体现

这一章对应岗位里的：

~~~树形
Agent harness 体系建设
上下文工程
工具设计
记忆与状态管理
错误恢复
评估与可观测
系统稳定性
~~~

先记住一句话：

~~~树形
Agent Harness = 围绕 LLM 搭的一整套执行安全带和工程外骨骼
~~~

更工程化地说：

~~~树形
LLM 本身只会生成文本 / tool_calls

Harness 负责：
├── 给模型准备上下文
├── 控制模型能用哪些工具
├── 执行工具
├── 管理状态
├── 处理审批
├── 处理失败
├── 保存 trace
├── 控制成本
├── 做评估
└── 把过程展示给用户
~~~

────────────────────────────────────────────────────

### 20.1 没有 Harness 的系统

~~~树形
用户输入
└── 直接发给 LLM
    └── LLM 返回文本

问题：
├── 没有稳定上下文
├── 没有工具权限控制
├── 没有状态持久化
├── 没有错误恢复
├── 没有审批
├── 没有 trace
├── 无法复盘
├── 无法评估
└── 无法稳定做复杂任务
~~~

这种更像 chatbot，不像 Agent 系统。

────────────────────────────────────────────────────

### 20.2 有 Harness 的系统

~~~树形
用户输入
│
└── Harness
    ├── Context Builder
    │   └── 准备 system prompt / history / memory / RAG
    │
    ├── Planner / Runner
    │   └── 控制模型调用和循环
    │
    ├── Tool Layer
    │   ├── 工具注册
    │   ├── 参数校验
    │   ├── 权限控制
    │   └── 工具执行
    │
    ├── State Manager
    │   ├── session state
    │   ├── run state
    │   └── resume state
    │
    ├── Safety / Approval
    │   ├── 高风险工具拦截
    │   └── 人工批准后恢复
    │
    ├── Observability
    │   ├── trace
    │   ├── events
    │   ├── tool calls
    │   └── cost / latency
    │
    └── Persistence
        ├── 保存 run
        ├── 保存 messages
        ├── 保存 tool result
        └── 保存最终状态
~~~

结论：

~~~树形
Harness 不是某一个类
Harness 是整套运行时框架
~~~

────────────────────────────────────────────────────

### 20.3 Harness 的核心模块

| Harness 模块 | 作用 | 本项目对应 |
|--------------|------|------------|
| Context Builder | 组装上下文 | RunContextFactory / ContextAssembler |
| Model Adapter | 屏蔽模型 API 差异 | ChatCompletionsAdapter |
| Runner Loop | 控制 Agent 循环 | AgentRunner |
| Tool Registry | 管理可用工具 | ToolRegistry |
| Tool Executor | 执行工具和审批 | ToolRunner / async_handle_tool_calls |
| Middleware | 沙箱、权限、拦截 | MiddlewarePipeline / SandboxMiddleware |
| State Manager | 会话状态 | RunState / SessionStore |
| Memory / Compact | 历史压缩 | CompactService / HistoryCompactor |
| Persistence | 终态落库 | RunRecorder |
| Trace | 可观测 | RunTraceStore / ToolTracer |
| Resume | 审批恢复 | ResumeRunService |
| Streaming | 实时输出 | RunSSEBridge / RunLifecycle |
| UI Feedback | 前端状态展示 | ToolCard / Trace Panel |

────────────────────────────────────────────────────

### 20.4 本项目如何体现 Harness 思想

#### 20.4.1 上下文工程

~~~树形
RunContextFactory
├── 读取 session record
├── 创建 model adapter
├── 读取 RunState
├── 自动 compact
├── 解析 effective_agent_name
├── 加载 AgentDefinition
├── 调 ContextAssembler
├── 解析 approval_policy
└── 返回 RunContext
~~~

Harness 体现：

~~~树形
模型不是裸跑
每次 run 前都先构造完整执行上下文
~~~

#### 20.4.2 工具控制

~~~树形
AgentRunner
└── build_model_request()
    ├── 根据 agent_profile.tool_names 暴露工具
    └── 不是把所有工具都给模型

ToolRunner
├── 校验工具是否允许
├── 判断风险
├── 触发审批
├── 执行工具
└── 返回 ToolBatchResult
~~~

Harness 体现：

~~~树形
LLM 只能请求工具
Runtime 决定工具是否真的执行
~~~

#### 20.4.3 状态管理

~~~树形
RunState
├── messages
└── step

SessionStore
├── save_state()
├── get()
└── read_session_state()

RunRecorder
└── run 完成后保存最终 state
~~~

Harness 体现：

~~~树形
多轮对话不是靠模型记住
而是系统保存状态，再喂回模型
~~~

#### 20.4.4 审批与恢复

~~~树形
工具需要审批
│
├── ToolRunner 生成 approval_required
├── ApprovalStore 保存 saved_messages
├── RunLifecycle 返回 paused
├── 前端显示审批按钮
│
└── 用户批准后
    ├── ResumeRunService 恢复 state
    ├── 执行被审批工具
    ├── 追加 tool_result
    └── 继续 AgentRunner
~~~

Harness 体现：

~~~树形
高风险动作可暂停
用户批准后可从断点继续
不是整轮重跑
~~~

#### 20.4.5 可观测 Trace

~~~树形
ToolTracer
├── on_tool_start
├── on_tool_finish
└── on_approval_required

RunTraceStore
├── save_run_trace
├── create_tool_call
├── finish_tool_call
└── append_run_events_partial
~~~

Harness 体现：

~~~树形
每次 Agent 做了什么都可追踪
失败可以复盘
评估可以基于 trace 做
~~~

#### 20.4.6 流式体验

~~~树形
RunSSEBridge
├── start 帧
├── delta 帧
├── thinking_delta 帧
├── run_event 帧
├── paused 帧
└── end 帧
~~~

Harness 体现：

~~~树形
Agent 执行不是黑盒等待
前端能实时看到文本、工具、审批和状态
~~~

#### 20.4.7 沙箱与安全

~~~树形
MiddlewarePipeline
└── SandboxMiddleware
    ├── 路径改写
    ├── 工作区限制
    ├── VFS staging
    └── 高风险写入隔离
~~~

Harness 体现：

~~~树形
LLM 不能随便改真实文件
工具执行被 runtime 安全层包住
~~~

────────────────────────────────────────────────────

### 20.5 Harness 和 Agent 的区别

| 名称 | 是什么 | 关注点 |
|------|--------|--------|
| LLM | 模型 | 生成文本 / tool_calls |
| Agent | 带目标和工具的运行体 | 完成任务 |
| Harness | 支撑 Agent 稳定运行的工程系统 | 上下文、工具、状态、安全、trace、恢复、评估 |

简单比喻：

~~~树形
LLM = 大脑
Agent = 会做事的人
Harness = 工作台 + 工具箱 + 安全规则 + 记录仪 + 流程系统
~~~

────────────────────────────────────────────────────

### 20.6 本项目还缺哪些 Harness 能力

已有：

~~~树形
已具备
├── Context assembly
├── Tool registry
├── Tool execution
├── Approval pause
├── Resume
├── Session state
├── Compact
├── Trace
├── Streaming
├── Sandbox
└── VFS staging
~~~

待补：

~~~树形
还可增强
├── Long-term memory
├── RAG retriever
├── MCP tool bridge
├── Agent Eval runner
├── Cost metrics
├── Latency metrics
├── Alerting
├── Queue / async task
├── Rate limit
└── A2A protocol bridge
~~~

────────────────────────────────────────────────────

### 20.7 面试表达

~~~text
我理解的 Agent harness 不是单个 prompt，也不是简单 tool calling。
它是围绕 LLM 构建的一整套运行时系统，负责上下文组装、模型适配、工具注册、权限审批、状态管理、错误恢复、trace 可观测、成本延迟监控和评估。

我的项目里已经体现了 harness 思想：
RunContextFactory 和 ContextAssembler 负责上下文工程；
AgentRunner 负责模型循环；
ToolRegistry 和 ToolRunner 负责工具调用；
MiddlewarePipeline 和 SandboxMiddleware 负责安全边界；
SessionStore、RunState、CompactService 负责状态和短期记忆；
RunRecorder、RunTraceStore、ToolTracer 负责持久化和可观测；
ResumeRunService 负责审批后的断点恢复。

所以它不是一个裸 LLM chatbot，而是一个有工具、有状态、有审批、有恢复、有 trace 的 Agent 执行引擎雏形。
~~~
