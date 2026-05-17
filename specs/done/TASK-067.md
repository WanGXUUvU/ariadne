# TASK-067 - 后端现有功能重构

## 目标
把当前后端从原型式 `runtime` 大包里拆出来，只重构现有功能，不新增能力，不改变现有产品行为。

## 产品层
Backend Architecture

## 我对当前项目的理解
现在这个项目已经不是纯原型了。

它已经有了这些真实能力：
- 会话创建、列表、读取、重置
- `/run` 主执行链路
- Trace 回放
- Skill 列表、启用、禁用、加载
- Tool Registry 和本地工具执行
- 历史压缩
- Agent 定义读取
- 前端工作台已经能把这些能力串起来

所以当前问题不是“功能少”，而是“功能已经多起来了，但目录还停留在原型阶段”。  
最明显的症状是 `runtime/` 里混入了很多不同职责的东西，导致后续继续加能力时，所有新逻辑都会往 `runtime` 里堆，结构会越来越难维护。

## 现状问题
- `runtime/` 里混了执行循环、模型调用、上下文构造、历史压缩、工具注册、Skill 加载和 Agent 定义加载。
- `services.py` 名字像服务层，但它其实承担的是应用编排。
- `core/model.adapter.py` 文件名不符合 Python 常规命名，也会持续制造理解成本。
- 现在的结构能跑，但已经不适合继续扩展。

## 官方建议的分层
按照职责拆成下面这些层：

- `api/`：HTTP 接口，只接收请求和返回响应
- `application/`：应用服务层，编排一次业务请求
- `runtime/`：Agent 执行循环，只负责 run loop
- `model/`：模型调用抽象，比如 `ModelAdapter`
- `context/`：prompt、messages、历史压缩、上下文构造
- `skills/`：skill 加载、skill registry、skill routing
- `tools/`：tool schema、tool registry、tool dispatcher、本地工具
- `storage/`：数据库、ORM、repository、store
- `core/`：通用领域类型、schema、协议、错误定义

## 当前主链路
只保留这一条主链路来判断分层是否合理：

`api -> application -> runtime -> model/context/tools/storage`

含义很简单：
- `api` 只负责接入
- `application` 只负责一次业务请求怎么编排
- `runtime` 只负责 Agent 怎么跑
- `model/context/tools/storage` 各司其职，不互相吞职责

## 现有文件归位
当前仓库里的文件，建议按下面方式重构。

| 当前文件 | 建议归位 | 说明 |
|---|---|---|
| `agent_prototype/api/app.py` | 保持 `api/app.py` | 应用入口，不要再拆散 |
| `agent_prototype/api/routes.py` | 后续拆成 `api/routes/*.py` | 路由会继续增长，单文件会越来越难维护 |
| `agent_prototype/runtime/agent.py` | `runtime/agent_runtime.py` 或 `runtime/agent_loop.py` | 真正的 Agent run loop |
| `agent_prototype/runtime/services.py` | `application/run_service.py` 等 | 这是应用编排，不是 runtime |
| `agent_prototype/runtime/llm_client.py` | `model/openai_adapter.py` 或 `model/adapter.py` | 模型调用边界应该从 runtime 里移走 |
| `agent_prototype/runtime/prompt_builder.py` | `context/prompt_builder.py` | prompt 构造属于上下文层 |
| `agent_prototype/runtime/compaction.py` | `context/compaction.py` | 历史压缩属于上下文层 |
| `agent_prototype/runtime/tool_registry.py` | `tools/registry.py` | 工具注册属于 tools |
| `agent_prototype/runtime/skill_loader.py` | `skills/loader.py` | Skill 加载属于 skills |
| `agent_prototype/runtime/skill_service.py` | `application/skill_service.py` 或 `skills/registry.py` | 如果是业务编排就进 application，如果是纯技能管理就进 skills |
| `agent_prototype/runtime/agent_loader.py` | `application/agent_definition_service.py` 或 `storage/agent_definition_store.py` | Agent 定义加载不应继续挂在 runtime |
| `agent_prototype/core/model.adapter.py` | 改名为 `model/adapter.py` | Python 文件名不要用点号分隔 |
| `agent_prototype/storage/session_store.py` | `storage/stores/session_store.py` 或 `repositories/session_repo.py` | 持久化逻辑归 storage |
| `agent_prototype/storage/agent_definition_store.py` | `storage/stores/agent_definition_store.py` | Agent 定义存储归 storage |
| `agent_prototype/tools_defs/*.py` | `tools/builtin/*.py` | 本地工具实现归 tools |

## 我建议的目录目标
不是一次把仓库彻底改成大工程模板，而是先把职责收口到位。

```text
agent_prototype/
├── api/
│   ├── app.py
│   ├── routes/
│   └── deps.py
├── application/
│   ├── run_service.py
│   ├── session_service.py
│   ├── skill_service.py
│   ├── trace_service.py
│   └── agent_definition_service.py
├── runtime/
│   ├── agent_runtime.py
│   └── agent_loop.py
├── model/
│   ├── adapter.py
│   ├── openai_adapter.py
│   ├── mock_adapter.py
│   ├── types.py
│   └── registry.py
├── context/
│   ├── context_builder.py
│   ├── prompt_builder.py
│   ├── compaction.py
│   ├── message_window.py
│   └── prompts.py
├── skills/
│   ├── loader.py
│   ├── registry.py
│   ├── router.py
│   ├── types.py
│   └── builtin/
├── tools/
│   ├── base.py
│   ├── registry.py
│   ├── dispatcher.py
│   ├── schemas.py
│   └── builtin/
├── trace/
│   ├── recorder.py
│   ├── event_types.py
│   └── serializers.py
├── storage/
│   ├── db.py
│   ├── models.py
│   ├── repositories/
│   └── stores/
├── core/
│   ├── schemas.py
│   ├── agent_definition.py
│   ├── tool_types.py
│   ├── message_types.py
│   ├── errors.py
│   └── ids.py
├── tests/
│   ├── test_agent_runtime.py
│   ├── test_model_adapter.py
│   ├── test_context_builder.py
│   ├── test_tool_dispatcher.py
│   └── test_skill_loader.py
└── frontend/
    └── src/
```

注意：
- 这不是要求现在一次性补齐所有新文件。
- 这是“现有功能未来应该归位到哪里”的目标图。
- 这里故意把 `storage`、`core`、`tools`、`trace`、`tests` 一起放进来，因为它们现在都已经是项目里的真实职责，不是可有可无的占位目录。
- 当前任务只做重构，不加新功能。

## 重构原则
1. 先按职责分层，不按文件名分层。
2. 一个文件只服务一个职责。
3. `runtime` 只留 Agent 执行循环。
4. 模型调用从 `runtime` 里移到 `model`。
5. prompt / 历史压缩移到 `context`。
6. Skill 相关逻辑移到 `skills`。
7. 工具注册和工具执行移到 `tools`。
8. 应用编排移到 `application`。
9. 存储与领域协议回到 `storage` / `core`。

## 重构顺序
这一步很关键，避免一次性大搬家把链路搞断。

### 第一波，先把 runtime 里最明显的异类职责拆出去
优先迁移：
- `runtime/llm_client.py`
- `runtime/prompt_builder.py`
- `runtime/compaction.py`
- `runtime/tool_registry.py`
- `runtime/skill_loader.py`

原因：
- 这几个文件最容易明确归类
- 迁出去后，`runtime` 会立刻变窄
- 先做这一步，收益最大，风险最小

### 第二波，再拆应用编排
迁移：
- `runtime/services.py`

原因：
- 这个文件不是 Agent loop 本身
- 它更像一次请求的业务调度器
- 归到 `application` 后，调用链会更清楚

### 第三波，再拆执行循环和定义加载
迁移：
- `runtime/agent.py`
- `runtime/agent_loader.py`
- `runtime/skill_service.py`

原因：
- `agent.py` 应该只保留 run loop
- `agent_loader.py` 更像定义服务或仓储适配
- `skill_service.py` 要看它到底是业务编排还是技能管理

### 第四波，整理命名和边界
处理：
- `core/model.adapter.py` 改名为 `model/adapter.py`
- `storage/session_store.py` 和 `storage/agent_definition_store.py` 重整到更清楚的位置
- `tools_defs/*.py` 迁到 `tools/builtin/*.py`

原因：
- 这一步是把结构和命名统一到同一套风格
- 让后续再加功能时，入口不再靠猜

## 实现步骤
1. 先以现有行为为基准，确认哪些功能必须原样保留。
2. 先迁移 `runtime` 中最明显的异类职责。
3. 再拆 `services.py` 到 `application/`。
4. 再处理 `agent.py`、`agent_loader.py`、`skill_service.py` 的职责切分。
5. 最后整理 `storage/`、`tools_defs/` 和 `core/model.adapter.py`。
6. 每一步都保持现有测试通过。

## 范围内
- 梳理 `api / application / runtime / model / context / skills / tools / storage / core` 的职责边界
- 把现有 `runtime/` 里多职责文件迁到更合适的层
- 保留当前已有功能和行为
- 只做重构和目录整理，不加新能力

## 范围外
- 不新增功能
- 不改产品行为
- 不改前端
- 不改数据库迁移逻辑
- 不引入新的模型能力

## 完成标准
- 每个目录的职责都能一句话说清
- `runtime` 收窄到 Agent 执行循环
- 现有功能没有丢失
- 目录结构明显比原型阶段清楚
- `runtime/` 不再承担模型调用、prompt 构造、历史压缩、工具注册和 skill 加载
- 新入口路径能看出层级，不再靠原型式目录命名猜职责

## 验证
- 现有测试通过

## Review 检查点
- 是否只重构现有功能，没有引入新能力
- 是否把 `runtime` 的职责收窄
- 是否没有破坏现有测试
