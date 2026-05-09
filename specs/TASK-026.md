# TASK-026 - Codex MCP Server 边界设计

## 目标
按 Codex 官方 MCP 形态，定义本项目里 `MCP server` 的配置边界、运行边界和接入顺序。

## 产品层
MCP / Tool Platform

## 背景
Codex 官方把 MCP 视为“连接外部工具和系统”的标准入口，优先解决 repo 外部上下文和外部工具接入问题。
当前项目已经有本地 `Tool Registry` 闭环，但还没有官方形态的 `MCP server` 配置层。
本任务先把“server 怎么声明、怎么启用、怎么暴露 tool”设计清楚，不直接开始真实接入。

## 范围内
- 定义与 Codex 官方对齐的 `mcp_servers.<id>` 配置模型
- 明确支持的 transport：`STDIO` 和 `Streamable HTTP`
- 明确 Phase 1 只接入 MCP `tools`
- 明确 `MCP server config -> discovered tools -> runtime tool surface` 的映射边界
- 明确 timeout、启停、tool allowlist/denylist、认证字段落在哪一层
- 明确 MCP tool 调用如何进入现有 trace / audit 闭环
- 产出后续实现任务卡

## 范围外
- 真正启动或连接 MCP server
- 接入 MCP `resources` / `prompts`
- UI 管理 MCP server
- OAuth 登录完整流程
- 插件 marketplace

## 官方对齐要求
- 以 Codex 官方 `mcp_servers.<id>` 配置思路为准，而不是自定义一套更简化的 server 结构
- Phase 1 必须明确区分“server 配置”和“server 暴露出的 tools”
- 设计时不把 MCP 直接塞进 Agent 定义层，仍保持统一工具入口

## 当前主链路
1. 用户或项目配置声明一个 `mcp_servers.<id>`
2. runtime 根据 transport 信息准备连接该 server
3. 从 server 发现可用 tools
4. 先应用 `enabled_tools` / `disabled_tools` 等 server 级过滤
5. 再把可暴露的 tool 映射进统一 runtime tool surface
6. Agent 继续像调用本地工具一样调用这些 MCP tools
7. tool 调用结果、错误和审批信息继续进入统一 trace

## 本任务只回答的核心问题
- `mcp_servers.<id>` 至少需要哪些字段
- server 级配置和 tool 级配置的边界在哪
- MCP tool 进入 runtime 时，哪些信息必须保留来源信息
- 审批、超时、错误、trace 分别发生在 client 层还是统一 runtime 层
- Phase 2 以后如果要接 `resources` / `prompts`，当前设计是否还能兼容

## 配置设计必须覆盖的字段
- `command`
- `args`
- `env`
- `env_vars`
- `cwd`
- `url`
- `enabled`
- `required`
- `startup_timeout_sec` / `startup_timeout_ms`
- `tool_timeout_sec`
- `enabled_tools`
- `disabled_tools`
- `bearer_token_env_var`
- `http_headers`
- `env_http_headers`
- `scopes`
- `oauth_resource`

## 实现步骤
1. 阅读当前 `runtime/tool_registry.py`、`runtime/agent.py`、trace schema，确认现有统一工具入口。
2. 写出本项目的 MCP server 配置草案，字段命名尽量与 Codex 官方一致。
3. 明确 server 配置对象和 discovered tool 对象不是同一个层级。
4. 定义 Phase 1 的 discovered tool 最小形态，至少包含来源 server、tool name、description、input schema。
5. 设计 MCP tool 映射到统一 runtime tool surface 的方式，要求不推翻本地工具入口。
6. 设计 timeout、错误、审批、trace 的挂载点。
7. 标注后续实现拆分：server config loader、MCP client adapter、tool bridge、trace/approval 扩展。

## 完成标准
- `mcp_servers.<id>` 的边界清楚，并与官方字段体系基本对齐
- 明确 Phase 1 只接 MCP `tools`
- 不把 MCP 直接揉进 Agent 定义
- 本地工具和 MCP 工具仍能共用统一调用入口
- 后续实现可以按小步任务拆开

## 验证
- 仅 Review

## Review 检查点
- 是否先定义了 server config，而不是直接跳到 tool wrapper
- 是否明确写出 Phase 1 只做 `tools`
- 是否保留了 `STDIO` 和 `Streamable HTTP` 两种 transport
- 是否把超时、allowlist/denylist、认证字段放在了 server 层
- 是否为后续 `resources` / `prompts` 留出了扩展位
