# TASK-053 - Chat Assistant Agent 定义

## 目标
为聊天助理创建专属的 Agent 定义文件，明确它的角色、能力边界和默认工具集，让它和未来的 Coding Agent 明确区分开。

## 产品线
聊天助理

## 范围内
- 在 `agents_defs/` 目录创建 `assistant.yaml`（或 JSON）
- 定义 name、description、system_prompt、tool_names、skill_names
- system_prompt 体现"通用助理"人格：友好、简洁、诚实
- 默认工具集：先仅使用已存在工具；`web_search` 等 `TASK-056` 完成后再加入
- 确认 Agent Loader 能正确读取此定义
- 写测试确认可以按名称加载

## 范围外
- 让 LLM 自动生成 system prompt
- 多语言 prompt
- 复杂人格配置 UI

## 实现步骤
1. 确认当前 `agents_defs/` 目录结构和 Agent Loader 格式。
2. 创建 `assistant.yaml`，填写基础字段。
3. 确认 Agent Loader 能扫描并加载它。
4. 在数据库或内存中注册 assistant agent。
5. 写测试：按 `agent_name=assistant` 运行一次，确认 system_prompt 正确注入。

## 完成标准
- 通过 `agent_name=assistant` 可以启动聊天助理模式。
- system_prompt 体现助理人格，而不是默认占位符。
- 和未来 `coding` agent 定义文件格式一致。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- YAML 格式是否和 loader 对齐。
- system_prompt 是否清晰定义助理边界。
- tool_names 是否只包含助理合适的工具。
