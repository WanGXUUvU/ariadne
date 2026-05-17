# TASK-070 - 架构优化

## 目标
在当前已经分层完成的基础上，继续压缩中心文件职责，让 `api` 和 `application` 更轻、更清楚，避免后续功能继续往少数大文件里回流。

## 产品层
Backend Architecture

## 我对当前项目的理解
当前项目已经不是原型式“杂糅目录”了，核心层次基本成立：
- `api/` 负责 HTTP 入口
- `application/` 负责业务编排
- `runtime/` 只保留 Agent 执行循环
- `model/`、`context/`、`skills/`、`tools/`、`storage/`、`core/` 已经分别落位
- `tests/` 也已经按模块拆开

但这只是“分层成立”，还不是“职责已经足够窄”：
- `api/routes.py` 仍然把多个资源接口放在一起
- `application/run_service.py` 仍然同时承担 session、compact、skill、agent、trace 相关编排
- `skills/skill_loader.py`、`tools/tool_registry.py` 还有继续收口空间
- `trace/` 目录目前还是占位，尚未形成独立的执行轨迹层

所以本次任务不是重做架构，而是在现有分层上继续做“减肥”和“切边界”。

## 当前架构图
主链路保持不变：

`api -> application -> runtime -> model / context / skills / tools / storage -> response`

每层当前的角色：
- `api`：只做 HTTP 适配
- `application`：只做一次业务请求的编排
- `runtime`：只做 Agent loop
- `model`：只做模型适配
- `context`：只做 prompt / 历史 / compact
- `skills`：只做 skill 扫描、加载、配置
- `tools`：只做 tool registry 和 builtin tools
- `storage`：只做数据库和持久化
- `core`：只做领域类型和协议

## 现状问题
- `api/routes.py` 过大，接口继续增长会更难维护。
- `run_service.py` 仍同时包含 session 读取、自动 compact、skill 加载、agent 定义加载、runtime 调用、trace/状态落库。
- `skills/skill_loader.py` 和 `tools/tool_registry.py` 虽然已经归位，但内部职责仍然偏集中。
- `trace/` 目录存在但没有真正落地，会让边界看起来比实际更完整。
- 目前的优化目标不是“更漂亮”，而是“把最容易回流的中心文件继续压窄”。

## 本次优化原则
1. 只优化现有能力的结构边界，不新增能力。
2. 优先拆中心文件，不优先动已经清楚的层。
3. 保持现有 API 行为不变。
4. 保持现有测试语义不变。
5. 机械迁移优先，避免重写逻辑。
6. 如果必须保留兼容入口，只保留短期 shim，不保留双份实现。

## 优化分层

### P0 - 先收窄 HTTP 入口
目标：让 `api/` 不再是一个“大路由文件”，而是按资源分开。

建议动作：
- 把 `agent_prototype/api/routes.py` 拆成 `api/routes/` 目录
- 按资源切分为：
  - `run_routes.py`
  - `session_routes.py`
  - `skill_routes.py`
  - `trace_routes.py`
  - `agent_routes.py`
- `api/routes.py` 如果保留，只做总装配或兼容入口

收益：
- 路由职责更清楚
- 每个接口组更容易定位
- 后续新增 API 不会继续堆在一个文件里

### P1 - 压缩应用编排层
目标：让 `application/run_service.py` 只保留 `/run` 的主编排，不继续吞别的职责。

建议动作：
- 把 `run_service.py` 中与 `/run` 无关的编排继续拆出
- 如果逻辑足够独立，考虑拆成：
  - `session_service.py`
  - `compact_service.py`
  - `trace_service.py`
  - `skill_service.py`
  - `agent_definition_service.py`
- 保持 `run_service.py` 的职责边界：输入请求 -> 组装上下文 -> 调用 runtime -> 持久化结果

收益：
- `/run` 主链路更容易读
- compact / skill / session 的职责更容易单测
- 以后加功能时不容易再把逻辑塞回 `run_service.py`

### P2 - 收紧技能与工具中心文件
目标：继续减少“一个文件里做太多件事”的情况。

建议动作：
- `skills/skill_loader.py`
  - 如果后续还有增长，继续拆扫描、frontmatter 解析、配置读写
- `tools/tool_registry.py`
  - 如果执行逻辑和注册逻辑继续膨胀，后续再考虑拆 dispatcher
- 这些动作只在职责继续扩大时做，不提前拆

收益：
- 中心模块更薄
- 保持当前可读性
- 不为了“看起来更细”而过度拆分

### P3 - 决定 `trace/` 是否真正落地
目标：避免一个目录只是占位。

两种路线二选一：
- 路线 A：把 `trace/` 真正补成执行轨迹 recorder / serializer / event types
- 路线 B：如果当前阶段还不需要，就明确保留占位，不再假装它已经是一层完整实现

建议：
- 先评估当前 `session_run_events`、`TraceResponse` 和未来 UI 需求
- 如果短期不扩展 trace 层，不要强行新增抽象

## 建议关注的文件
| 当前文件 | 优化方向 | 是否优先动 |
|---|---|---|
| `agent_prototype/api/routes.py` | 按资源拆路由 | 是 |
| `agent_prototype/application/run_service.py` | 只保留 `/run` 主编排 | 是 |
| `agent_prototype/application/skill_service.py` | 视增长再拆 | 否 |
| `agent_prototype/skills/skill_loader.py` | 视增长再拆 | 否 |
| `agent_prototype/tools/tool_registry.py` | 视增长再拆 | 否 |
| `agent_prototype/trace/` | 决定是否落地 | 视需求 |

## 范围内
- 拆路由
- 拆应用编排
- 收紧中心文件
- 修复 import
- 必要时保留短期兼容 shim

## 范围外
- 不新增能力
- 不改 API 行为
- 不改数据库结构
- 不改前端
- 不引入新框架
- 不重写业务逻辑

## 实施顺序
1. 先拆 `api/routes.py`。
2. 再压缩 `application/run_service.py`。
3. 再评估 `skills/skill_loader.py` 和 `tools/tool_registry.py` 是否还要继续切边界。
4. 最后决定 `trace/` 是否真正落地。

## 完成标准
- `api/routes.py` 不再是明显的“大而全”入口。
- `run_service.py` 的职责边界更单一。
- 现有分层仍然成立，没有回流。
- 现有测试通过。
- 优化后的结构仍然能用一句话解释每层职责。

## 收口
本卡已完成并收口。

- `api/routes.py` 已按资源拆分到 `api/routes/`。
- `application/run_service.py` 已收窄为 `/run` 主编排。
- `compact`、`run`、`trace`、`reset`、`delete` 等主链路已验证可用。
- 全量测试通过，现有分层边界没有回流。

## 验证
- `python3 -m unittest discover -s agent_prototype/tests -p 'test_*.py' -v`
