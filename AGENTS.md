# AGENTS.md

## 1. 核心规范 (Standards)
*   **边界与极致分层**：单文件只做一件事。写代码前必先厘清本层职责（负责/不负责、输入/输出、上下游流向）。
*   **敏捷切片迭代**：小步快跑，一次仅推进一个最小文件或最小切片。
*   **长期演进**：逐步演进为具备 tool calling、session/workspace、skill 动态加载与可追溯执行 of 工业级产品。

---

## 2. 双轨工作模式 (Double-Track Mode)

### 🟢 后端 (Backend) —— 教学导向 (Coach Mode)
*   **非请勿动**：非明确命令“直接改代码”或“start-implementation”时，**绝对禁止**直接修改后端 Python 逻辑。
*   **互动式逐层教学规范 (Interactive & Comparative)**：
    1. **高阶重构策略与拓扑**：首先说明本次大版本重构的整体架构修改思路（起因、终点、链路拓扑图）。
    2. **互动式逐层推进**：**一次只给出一个层级的修改细节**。严禁一次性倾倒所有文件或所有层级的代码。当前层级用户修改完成并确认（或通过单测验证）后，再进入下一层级教学。
    3. **链路对比剖析 (Link Before/After)**：在给出每一层代码前，必须对比：
        *   **原有链路 (Before)**：原先的数据怎么流、逻辑是什么、有什么局限性。
        *   **修改后链路 (After)**：修改后数据怎么流、逻辑是什么、如何解决局限性。
        *   **修改原因 (Why)**：为什么在这里改，不在别处改的深层设计决策。
        *   **前端视觉映射 (Visual link)**：用户在前端界面能看到什么样的视觉状态或交互反馈。
    4. **精确 Drop-in 代码**：给出带行号的文件链接，以 `# ── 修改目标位置 ──────────────────` 锚点提供 drop-in 代码。
    5. **单测守航验证**：提供当前层级一键复制运行的单测命令，由用户运行确保 100% 绿灯。

### 🪐 前端 (Frontend) —— 效率导向 (Auto Mode)
*   **效率至上**：收到修改指令或 `start-implementation`，直接重构、编写、打包 Vue 3 / TS 代码，确保打包 100% 通过。

---

## 3. 工作流与启动 (Workflow & Startup)
*   **启动与推进**：启动必读 `AGENTS.md` -> `STATUS.md` -> 当前任务卡。只推进当前指向的单张任务卡（允许基于专业理解自主重构任务卡），绝不主动扩展。
*   **指令语义**：`create-task`（只建卡不实现）；`start-implementation`（启动自动改/教学改）；`review`/`coach`（只检查教学不改代码）。
*   **新任务拆解模板**：
    ```text
    用户动作：
    用户会看到：
    新数据从哪里产生 / 存在哪里：
    前端调哪个接口 / need改的层：
    ```

---

## 4. 项目结构 (Project Structure)

```
Ariadne/
├── backend/            ← Python 后端
│   ├── agent/                  # Agent 定义与类型
│   ├── api/                    # FastAPI 路由 + DTO schemas
│   │   ├── routes/             # run, settings, tools, approval, compact
│   │   └── dto/schemas.py      # 纯 HTTP I/O 类型
│   ├── context/                # ContextAssembler, compaction, skill_context
│   ├── core/                   # 核心类型 + adapters
│   ├── execution/              # 运行时引擎
│   │   ├── runtime/            # agent_runtime, execution_session, vfs
│   │   ├── resume/             # 恢复执行服务
│   │   ├── persistence/        # 持久化类型
│   │   └── streaming/          # SSE 流式输出
│   ├── infra/db/               # 数据库引擎 + migrations
│   ├── memory/                 # 记忆模块
│   ├── model/types/            # 领域模型类型
│   ├── observation/            # ToolRunObserver, tracer, logger
│   ├── planning/               # 规划模块
│   ├── prompt/                 # Prompt builder
│   ├── security/               # 安全中间件 + sandbox
│   │   ├── middleware/         # BaseMiddleware, ApprovalMiddleware, SandboxMiddleware
│   │   └── sandbox/            # SandboxPathResolver
│   ├── skills/                 # Skill loader + types
│   ├── tools/                  # 工具系统
│   │   ├── builtin/            # 内置工具 (filesystem, search, agent_bridge, util)
│   │   ├── registry.py         # ToolRegistry 注册中心
│   │   ├── types.py            # ToolDefinition + RiskLevel
│   │   └── result_types.py     # ToolResult, ToolError, 状态常量
│   └── tests/                  # 单元 + 集成测试
├── src/                        ← Vue 3 前端
│   ├── components/             # UI 组件
│   ├── composables/            # 状态管理 composables
│   └── views/                  # 页面视图
├── specs/                      # 任务卡 (TASK-XXX.md)
│   └── done/                   # 已完成任务卡归档
├── STATUS.md                   # 当前状态唯一权威入口
├── AGENTS.md                   # 本文件
└── package.json                # 前端依赖
```

### 架构分层 (L1-L8)

| 层 | 名称 | 职责 |
|----|------|------|
| L1 | API 路由 | HTTP 请求/响应，参数校验 |
| L2 | 应用服务 | 编排业务流程，无状态 |
| L3 | 工具系统 | ToolRegistry + 桥接回调 |
| L4 | 安全中间件 | 责任链：Sandbox → Approval |
| L5 | 执行引擎 | Agent runtime + VFS + streaming |
| L6 | 上下文装配 | ContextAssembler 统一组装 |
| L7 | 持久化 | DB + VFS 事务 (staged → commit/rollback) |
| L8 | 基础设施 | SQLite, LLM API adapter |

---

## 5. 常用命令 (Commands)

### 后端 (Python)

```bash
# 运行所有单元测试
python3 -m unittest discover -s backend/tests -p 'test_*.py' -v

# 运行特定测试文件
python3 -m unittest backend.tests.integration.test_agent_api -v

# 代码风格检查
black backend/ --check
ruff check backend/

# 编译检查（语法 + import）
python3 -m compileall backend/

# 启动后端服务
cd backend && python3 -m api.app
```

### 前端 (Vue 3 + TypeScript)

```bash
npm run dev       # 开发服务器
npm run build     # 生产构建（必须通过）
npm run lint      # 代码检查
```

### 一键验证（改完代码后跑）

```bash
# 后端：测试 + 编译
python3 -m compileall backend/ && python3 -m unittest discover -s backend/tests -p 'test_*.py' -v

# 前端：构建
npm run build
```

---

## 6. 关键设计决策

- **VFS staging 三态**：写操作先进入 `staged` 区，run 成功 → `commit` 落盘，失败/取消 → `rollback` 丢弃。保证工具写操作的原子性。
- **ToolRegistry.clone()**：每次 run 拷贝注册表副本，避免并发 run 间工具定义互相污染。浅拷贝足够（ToolDefinition 是 frozen 的）。
- **异常分层**：`execute_tool_call` 三层 try/except —— JSON 解析 → TypeError → Exception，每层返回不同错误码，不抛异常搞挂 Agent 循环。
- **闭包依赖注入**：子 Agent 桥接工具通过闭包注入回调（child_dispatcher, status_checker, child_waiter），工具函数本身不依赖全局状态。
- **inspect.signature 运行时反射**：检查 handler 签名是否含 `__context__`，按需注入上下文，不强求所有工具接受不用的参数。
