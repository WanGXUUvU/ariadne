# TASK-075 - 双轨产品共享底座：AGENTS.md规则引擎与动态多中间件机制

## 1. 目标 (Goal)
升级共享底座内核（Core Engine），完美落地“一底座、双子产品”的五项核心设计规范：
1. **空间规则引擎（Rulebook Unity）**：无论何种空间目录，运行时自动读取根目录下的 `AGENTS.md` 规则文本，并注入为系统最高约束指令。
2. **动态多中间件阵容（Tailored Middleware）**：
   - 编码会话（`coding`）：装配 `[SandboxMiddleware, ApprovalMiddleware]`；
   - 助理会话（`assistant`）：装配 `[ApprovalMiddleware]`，对高危文件/外发操作执行阻断审批。
3. **用户授权工具制（User-Delegated Tooling）**：智能体可用工具名单完全由用户在前端勾选，运行时由安全校验层强行拦截越权调用（`TOOL_NOT_ALLOWED`）。
4. **双轨会话解耦（Dual Session Routing）**：明确区分内置高工智能体（服务于编码产品）和自定义助理智能体（服务于助理产品）。
5. **心智提示词分级（Steering Prompt Differentiation）**：
   - 编码智能体（`coding`）：具有底座内置的、高度专业的软件工程基准系统提示词（Core Software Engineer Prompt）指导开发和代码 diff 规范；
   - 助理智能体（`assistant`）：底座零预设人设提示词（白板模式 Tabula Rasa），其人设与角色定位 100% 由用户自定义的 `System Prompt` 或本地空间心智文件（`SOUL.md` / `AGENTS.md`）绝对掌控，杜绝冲突。

---

## 2. 新任务拆解模板 (Task Teardown Template)

```text
用户动作：
1. 用户在拥有 AGENTS.md 的工作区内新建会话或发问。
2. 用户在 AgentManager 面板勾选/编辑智能体的工具权限。
3. 用户在助理会话或编码会话中触发敏感工具（如 send_email 或 bash_execute）。

用户会看到：
1. 智能体回答的行为完全遵从本地 AGENTS.md 写入的定制化规范。
2. 即使是助理会话，遇到高危操作时，前端依然会弹出亮起的 ApprovalCard 审批对话框，非敏感操作则静默秒出。
3. 试图执行未被用户授权的工具时，系统安全报错并友好提示。

新数据从哪里产生：
1. 会话建立时前端传入的会话类型标识（session_type: "coding" | "assistant"）。
2. 自定义智能体编辑保存时传入的授权工具名称列表（tool_names: string[]）。

新数据要存在哪里：
1. SQLite 数据库的 session_records 表（新增/使用 session_type 列）。
2. SQLite 数据库的 agent_definitions 表（更新 tool_names 列）。

前端调哪个接口：
1. 创建会话：POST /sessions （Payload 包含 session_type 与 workspace_path）。
2. 流式问答：POST /run/stream。
3. 智能体保存：POST /agents 或 PUT /agents/{id} （Payload 包含 tool_names）。

need改的层：
1. 业务上下文层 (run_context_builder.py)：自动定位工作区根目录读取并解析 AGENTS.md，合并装配入 System Prompt。
2. 运行中间件层 (sandbox.py & base.py)：SandboxMiddleware 精准拦截未授权工具（allow_tool_names 比对）；底座动态编排中间件管道。
3. 接口与服务层 (session_service.py & run_service.py)：会话落库增加类型，运行流式分发动态选择 Pipeline 组合。
```

---

## 3. 切片迭代路线 (Checklist)

- [ ] **切片 1：双轨提示词拼接分级与本地规则注入**
  - [ ] 在 `backend/application/services/run/run_context_builder.py` 中重构提示词组装逻辑：
    - 编码会话 (`session_type == "coding"`)：加载内置的、极其专业的软件开发系统提示词（`BUILTIN_SOFTWARE_ENGINEER_PROMPT`），并动态合并工作区根目录的 `AGENTS.md` 规则。
    - 助理会话 (`session_type == "assistant"`)：底座**零预设任何性格/人设系统提示词（白板无界模式）**，其心智提示词 100% 动态读取用户自定义字段（`AgentRecord.system_prompt`）以及空间心智文件（`SOUL.md` / `AGENTS.md` / `USER.md`）进行干净的初始化组装，彻底避免人设冲突。
  - [ ] 在 `run_context_builder.py` 中增加对 `AGENTS.md` / `SOUL.md` / `USER.md` 等工作区文件的检测、加载和解析逻辑，使用特定 XML 隔离标签包裹并压在提示词尾部保证最高优先级。
  - [ ] 编写对应的单元测试，验证双轨会话在心智提示词拼装和空间规则文件注入上的隔离行为完全符合预期。

- [ ] **切片 2：动态中间件编排与智能体双轨解耦路由（Coding vs Assistant）**
  - [ ] 扩展 `session_records` 表及 DTO，支持 `session_type` ("coding" | "assistant") 字段落库与序列化。
  - [ ] **实现智能体双轨解耦路由机制**：
    - 在创建 `coding` 开发会话时，默认且强行关联底座内置的、全量工具链的 `"Software Engineer"` 专业智能体定义；
    - 在创建 `assistant` 个人助理会话时，允许自由关联用户通过 `AgentManager` 雇用/创建的自定义智能体记录，并拉取其专属配置的受限工具名单。
  - [ ] 重构 `backend/application/services/run/run_service.py` 或 pipeline 组装逻辑：
    - `session_type == "coding"`：装配 `[SandboxMiddleware, ApprovalMiddleware]`。
    - `session_type == "assistant"`：仅装配 `[ApprovalMiddleware]`。
  - [ ] 运行单测验证不同会话类型下，工具执行经过的中间件链路完全符合预期。


- [ ] **切片 3：双轨子产品前端整合验证**
  - [ ] 前端调用 `POST /sessions` 时根据当前模式（开发工作台 vs 个人助理）正确传参 `session_type`。
  - [ ] 在前端进行流式运行与敏感工具测试，验证双子星产品的体验完全对齐。
  - [ ] 保证全量打包 `npm run build` 100% 通过。
