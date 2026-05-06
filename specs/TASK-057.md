# TASK-057 - Coding Agent 定义

## 目标
为编码产品创建专属的 Agent 定义，明确它的角色是"在用户代码库里帮助读取、理解、提议修改代码"，工具集和 system_prompt 都和聊天助理明确区分。

## 产品线
编码产品

## 范围内
- 在 `agents_defs/` 创建 `coding.yaml`
- system_prompt 体现编码助理人格：精准、谨慎、先读后改
- tool_names 包含：`list_files`、`read_file`、`search_text`、`propose_file_change`
- 不默认开放 `shell_exec`（需要显式权限）
- 写测试确认可以按 `agent_name=coding` 加载

## 范围外
- 自动生成 system_prompt
- 多语言定义
- 复杂权限 UI

## 实现步骤
1. 确认 `agents_defs/` 目录和 loader 格式（复用 TASK-053 建立的规范）。
2. 创建 `coding.yaml`，填写字段。
3. system_prompt 要求 agent：优先阅读文件、改前先确认路径、提议修改而非直接写入。
4. 确认 Coding Agent 和 Assistant Agent 在 API 中可以分别被选择。
5. 写测试。

## 完成标准
- 通过 `agent_name=coding` 启动编码 agent 模式。
- system_prompt 不同于 assistant，强调"谨慎操作文件"。
- tool_names 只包含安全的文件操作工具。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- system_prompt 是否明确禁止直接写文件（要走 propose 流程）。
- tool_names 是否排除了 shell_exec。
- 是否复用已有 loader，不重复造轮子。
