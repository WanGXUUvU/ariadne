# TASK-025 - Plugin 包格式

## 目标
设计项目自己的插件包格式，向 OpenCode 的插件分发思路靠拢。

## 产品层
Plugin Platform

## 范围内
- 定义 `.agent-plugin/plugin.json`
- 插件内可包含 skills
- 插件内可包含 agents
- 插件内可包含 MCP 配置占位
- 插件内可包含 assets 占位
- 本地加载插件 metadata

## 范围外
- 远程安装
- marketplace
- 安全签名
- 插件版本升级

## 实现步骤
1. 设计 plugin manifest 字段：name、version、description、skills、agents。
2. 创建示例插件目录。
3. 实现本地 plugin metadata loader。
4. 将插件 skills 和 agents 加入索引。
5. 测试坏 manifest 不影响主流程。

## 完成标准
- 本地插件可以被发现。
- 插件里的 skill 和 agent 可以进入对应列表。
- manifest 格式简单可扩展。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- 是否和普通 skill 机制复用。
- manifest 是否过度复杂。
- 插件路径是否安全。
