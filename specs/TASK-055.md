# TASK-055 - MCP Server 配置加载与发现

## 目标
在 `TASK-054` 的边界设计基础上，实现 `mcp_servers` 配置加载与 MCP tool discovery 的最小闭环。

## 产品层
MCP / Tool Platform

## 依赖
- `TASK-054` MCP 边界设计

## 范围内
- 定义 `mcp_servers` 配置 schema 和 loader
- 支持从项目配置和插件 `.mcp.json` 读取 server 配置
- 支持 `STDIO` 和 `Streamable HTTP` 两种 transport 的最小连接准备
- 启动或连接 server 后发现可用 `tools`
- 应用 `enabled_tools` / `disabled_tools`
- 产出 discovered tool metadata，供后续 runtime bridge 使用

## 范围外
- 真正把 MCP tool 接进 `ToolRegistry`
- 接入 `resources` / `prompts`
- OAuth 完整登录 UI
- MCP server 管理界面

## 实现步骤
1. 定义 `mcp_servers` Pydantic schema。
2. 读取项目配置和插件 `.mcp.json`，统一成 server config 列表。
3. 校验 transport、认证、timeout、enabled/required 等字段。
4. 建最小 MCP client adapter，连接 server 并读取 tool list。
5. 把 discovery 结果规范成内部 metadata 对象。
6. 写测试覆盖坏配置、禁用 server、discover 失败和 allowlist/denylist。

## 完成标准
- `mcp_servers` 可以被稳定读取和校验。
- runtime 能发现 MCP tools，但尚未暴露给 Agent。
- discovered tool metadata 结构稳定，能供下一张卡继续接入。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- server config 来源是否清楚。
- discovery 层是否还没越界到 runtime tool 执行。
- transport 和 timeout 是否放在 server 层处理。
