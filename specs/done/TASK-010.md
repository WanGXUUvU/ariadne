# TASK-010 - 统一 Tool Registry

## 目标
把本地工具整理成统一注册入口，为后续 MCP、插件工具、Skill 工具约束做准备。

## 产品层
Tool Registry

## 范围内
- 定义工具注册结构
- 把 `echo_tool` 放进 registry
- 提供 `get_tool_schemas(tool_names=None)`
- 提供 `execute_tool_call(name, arguments)`
- 保持现有工具调用行为不变

## 范围外
- MCP 工具
- 外部 HTTP 工具
- 工具权限系统
- 并行工具调用

## 实现步骤
1. 新建 `tool_registry.py`。
2. 定义 `ToolDefinition`，包含 name、schema、handler。
3. 将 `echo_tool` 注册进去。
4. 修改 Agent 主循环，删除 `if tool_name == "echo_tool"` 这种分支。
5. 让 LLM tools schema 从 registry 获取。
6. 测试未知工具返回稳定错误。

## 完成标准
- `Agent` 不再直接判断具体工具名。
- 新增工具只需要注册，不需要改 agent 主循环。
- 现有工具调用测试通过。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- registry 是否足够简单。
- 工具 schema 和 handler 是否绑定清楚。
- unknown tool 是否不会崩溃。
