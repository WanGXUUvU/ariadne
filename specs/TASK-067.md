# TASK-067 - 后端现有功能重构

## 目标
把当前后端从原型式 `runtime` 大包里拆出来，只重构现有功能，不新增能力。

## 产品层
Backend Architecture

## 现状问题
- `runtime/` 里混了执行循环、模型调用、上下文构造、历史压缩、工具注册、Skill 加载和 Agent 定义加载。
- 这些职责不是同一层，放在一起会让入口越来越难懂。
- 当前问题不是功能缺失，而是职责边界失焦。

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

## 现有文件归位
当前仓库里的这些文件，建议按下面方式重构：

| 当前文件 | 建议归位 | 原因 |
|---|---|---|
| `agent_prototype/api/app.py` | 保持 `api/app.py` | 应用入口 |
| `agent_prototype/api/routes.py` | 后续拆成 `api/routes/*.py` | 路由多了以后不要全放一个文件 |
| `agent_prototype/runtime/agent.py` | `runtime/agent_runtime.py` 或 `runtime/agent_loop.py` | 真正的 Agent Loop |
| `agent_prototype/runtime/services.py` | `application/run_service.py` 等 | 这是应用编排，不是 runtime |
| `agent_prototype/runtime/llm_client.py` | `model/openai_adapter.py` 或 `model/adapter.py` | 模型调用边界 |
| `agent_prototype/runtime/prompt_builder.py` | `context/prompt_builder.py` | prompt 构造属于 context |
| `agent_prototype/runtime/compaction.py` | `context/compaction.py` | 历史压缩属于 context |
| `agent_prototype/runtime/tool_registry.py` | `tools/registry.py` | 工具注册属于 tools |
| `agent_prototype/runtime/skill_loader.py` | `skills/loader.py` | skill 加载属于 skills |
| `agent_prototype/runtime/skill_service.py` | `application/skill_service.py` 或 `skills/registry.py` | 看它负责业务还是底层管理 |
| `agent_prototype/runtime/agent_loader.py` | `application/agent_definition_service.py` 或 `storage/agent_definition_store.py` | Agent 定义加载不属于 runtime |
| `agent_prototype/core/model.adapter.py` | 改名为 `model/adapter.py` | 文件名不要用 `model.adapter.py` |
| `agent_prototype/storage/session_store.py` | `storage/stores/session_store.py` 或 `repositories/session_repo.py` | 持久化逻辑 |
| `agent_prototype/storage/agent_definition_store.py` | `storage/stores/agent_definition_store.py` | Agent 定义存储 |
| `agent_prototype/tools_defs/*.py` | `tools/builtin/*.py` | 工具实现更清晰 |

## 当前重构主链路
只保留这一条主链路来判断分层是否合理：

`api -> application -> runtime -> model/context/tools/storage`

## 重构顺序
按这个顺序做，避免一次性大搬家：

1. 先收窄 `runtime/` 的职责，只保留 Agent run loop。
2. 再把模型调用移到 `model/`。
3. 再把 prompt / compact / message 构造移到 `context/`。
4. 再把 skill 相关逻辑移到 `skills/`。
5. 再把工具注册和本地工具移到 `tools/`。
6. 再把服务编排移到 `application/`。
7. 最后整理 `storage/` 和 `core/` 的边界。

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

## 实现步骤
1. 先按职责而不是按现有文件名梳理后端层次。
2. 先迁移 `runtime` 中最明显的异类职责，优先是 `llm_client.py`、`prompt_builder.py`、`compaction.py`、`tool_registry.py`、`skill_loader.py`。
3. 再拆 `services.py`，把应用编排搬到 `application/`。
4. 再处理 `agent.py` 和 `agent_loader.py`，把执行循环和定义加载拆开。
5. 再整理 `storage/`、`tools_defs/` 和 `core/model.adapter.py` 的命名。
6. 每一步都保持现有测试通过。

## 完成标准
- 每个目录的职责都能一句话说清。
- `runtime` 收窄到 Agent 执行循环。
- 现有功能没有丢失。
- 目录结构明显比原型阶段清楚。
- `runtime/` 不再承担模型调用、prompt 构造、历史压缩、工具注册和 skill 加载。
- 新入口路径能看出层级，不再靠原型式目录命名猜职责。

## 验证
- 现有测试通过。

## Review 检查点
- 是否只重构现有功能，没有引入新能力。
- 是否把 `runtime` 的职责收窄。
- 是否没有破坏现有测试。
