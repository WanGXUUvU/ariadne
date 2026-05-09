# TASK-056 - MCP Tool Bridge 与运行时接入

## 目标
把 discovered MCP tools 映射进现有统一工具入口，让 Agent 能像调用本地工具一样调用 MCP tools。

## 产品层
MCP / Runtime

## 依赖
- `TASK-055` MCP Server 配置加载与发现

## 范围内
- 定义 discovered MCP tool 到统一 runtime tool surface 的映射
- 保留 tool 来源信息，例如 `source_type`、`server_id`
- 把 MCP tool 暴露给现有 `ToolRegistry`
- 执行 MCP tool call，并返回统一 `ToolResult`
- 把 timeout、错误和审批信息接入现有 trace

## 范围外
- MCP `resources` / `prompts`
- MCP OAuth 完整交互
- 插件 marketplace
- 多 server 并发优化

## 实现步骤
1. 扩展统一工具定义，补齐来源信息。
2. 定义 MCP tool bridge，把 discovered tool 包成可执行 runtime tool。
3. 在执行链路里调用 MCP client，转换成统一 `ToolResult`。
4. 在 `AgentEvent` / trace 中补齐 MCP 来源和错误信息。
5. 写测试覆盖成功、tool error、timeout、server 不可用和 unknown tool。

## 完成标准
- Agent 能通过统一入口调用 MCP tools。
- 本地工具和 MCP 工具共用同一套事件和错误结构。
- trace 能区分工具来源，不再把 MCP tool 当成本地 handler。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- 是否保留了统一工具入口。
- MCP tool 来源信息是否完整。
- 错误和 timeout 是否没有散落到多层。
