# TASK-027 - Codex Plugin 包结构对齐

## 目标
按 Codex 官方插件结构，定义本项目的插件包格式和本地加载边界。

## 产品层
Plugin Platform

## 背景
Codex 官方里，插件是安装和分发单位，skill 是工作流作者格式，MCP server 和 app/connector 可以作为插件内组件被一起分发。
当前任务卡里自定义了 `.agent-plugin/plugin.json` 这套结构，和官方目录名、文件名不一致，需要收回到官方形态。

## 范围内
- 定义 `.codex-plugin/plugin.json` 为插件入口
- 支持插件根目录下的 `skills/`
- 支持插件根目录下的 `.mcp.json`
- 支持插件根目录下的 `.app.json`
- 支持插件根目录下的 `hooks/hooks.json`
- 支持插件根目录下的 `assets/`
- 设计本地 plugin metadata loader
- 设计 manifest 如何引用 `skills`、`mcpServers`、`apps`、`hooks`

## 范围外
- 远程安装
- marketplace
- 安全签名
- 插件版本升级
- 真正执行 MCP server
- 真正执行 app/connector

## 官方对齐要求
- 不再使用 `.agent-plugin/plugin.json`
- `plugin.json` 只放在 `.codex-plugin/` 下
- `skills/`、`.mcp.json`、`.app.json`、`hooks/`、`assets/` 保持在插件根目录
- 插件是分发单位，不重新发明一套和官方冲突的结构

## 当前主链路
1. 本地扫描插件目录
2. 读取 `.codex-plugin/plugin.json`
3. 解析 manifest 中引用的 `skills`、`mcpServers`、`apps`、`hooks`
4. 读取对应组件 metadata
5. 把 skill 进入 skill 索引
6. 把 `.mcp.json` 交给后续 MCP server 配置层
7. 把 `.app.json` 交给后续 app/connector 配置层

## manifest 第一版应覆盖的字段
- `name`
- `version`
- `description`
- `author`
- `homepage`
- `repository`
- `license`
- `keywords`
- `skills`
- `mcpServers`
- `apps`
- `hooks`
- `interface`

## 目录结构基线
- `.codex-plugin/plugin.json`
- `skills/<skill-name>/SKILL.md`
- `.mcp.json`
- `.app.json`
- `hooks/hooks.json`
- `assets/`

## 实现步骤
1. 先按官方目录结构重写任务定义和示例目录。
2. 设计 `plugin.json` 最小 manifest schema。
3. 设计本地 loader：先只校验 manifest 和组件路径，不执行组件。
4. 先接 skill metadata 索引，MCP 和 apps 只做 metadata 透传。
5. 坏 manifest、坏路径、缺文件不应打断主流程。

## 完成标准
- 本地插件目录结构与 Codex 官方基本一致
- skill、MCP server、app config 的装配边界清楚
- plugin loader 可以读取 metadata，但不会越权执行组件
- manifest 格式简单且后续能扩展

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- 是否仍然使用了官方目录名 `.codex-plugin`
- 是否把 `.mcp.json` 当作真实组件配置，而不是“占位”
- 是否区分了“plugin 是分发单位”与“skill 是作者格式”
- 是否避免把插件 loader 直接写成运行时执行器
