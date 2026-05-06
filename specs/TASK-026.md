# TASK-026 - MCP 边界设计

## 目标
定义 MCP 在本项目里的边界，明确什么时候接入、怎么映射到 Tool Registry。

## 产品层
MCP / Tool Platform

## 范围内
- 设计 MCP server 配置结构
- 设计 MCP tool 到本地 ToolDefinition 的映射
- 明确错误、权限、trace 的映射方式
- 产出后续实现任务卡

## 范围外
- 真正接入 MCP server
- UI 管理 MCP
- 插件 marketplace

## 实现步骤
1. 阅读当前 Tool Registry 结构。
2. 定义 MCP 工具最小字段：server、name、schema、description。
3. 设计映射到 `ToolDefinition` 的方式。
4. 明确权限判断发生在 registry 之前还是之后。
5. 写成设计说明并创建后续任务卡。

## 完成标准
- MCP 接入点清楚。
- 不需要推翻 Tool Registry。
- 后续能小步实现。

## 验证
- 仅 Review。

## Review 检查点
- 是否没有把 MCP 直接塞进 Agent。
- 是否保留本地工具和 MCP 工具统一入口。
- 权限和 trace 是否考虑到。

