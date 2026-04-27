# TASK-011 - Skill 允许工具列表

## 目标
让 Skill 可以声明自己允许使用哪些工具，Agent 只把允许的工具暴露给模型。

## 产品层
Skill / Tool Registry

## 范围内
- `SKILL.md` 支持 `allowed_tools`
- loader 解析 allowed tools
- Agent 根据 skill 过滤 tools schema
- 执行时再次校验工具是否允许

## 范围外
- 权限审批
- MCP 工具
- UI 编辑 allowed tools

## 实现步骤
1. 扩展 `SKILL.md` 格式，给 default skill 加 `allowed_tools`。
2. 扩展 `Skill` 数据结构。
3. loader 解析 allowed tools。
4. `get_tool_schemas(tool_names=...)` 只返回允许工具。
5. 执行工具前检查 tool name 是否在允许列表。
6. 测试允许工具和禁止工具两条路径。

## 完成标准
- skill 可以限制模型看到的工具。
- 即使模型伪造 tool call，也会被 runtime 拦截。
- default skill 仍能使用 `echo_tool`。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- 是否同时做了暴露前过滤和执行前校验。
- allowed tools 缺省值是否安全。
- 错误事件是否可追踪。
