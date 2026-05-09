# TASK-044 - 文件工作区只读工具

## 目标
加入最小文件工作区能力，让 agent 能安全读取项目文件，但暂时不能写文件。

## 产品层
Workspace / Tools

## 背景
Codex 类产品的核心能力之一是理解代码库。第一步不做写入，只做可控的 list/read/search。

## 范围内
- 定义 workspace root，默认是项目根目录
- 新增 `list_files` 工具
- 新增 `read_file` 工具
- 新增 `search_text` 工具
- 阻止访问 workspace root 之外的路径
- 把文件读取事件写入 trace

## 范围外
- 写文件
- 删除文件
- shell 命令
- 大文件智能截断策略的完整实现

## 实现步骤
1. 新建 `workspace.py`，集中处理路径安全。
2. 实现 `resolve_workspace_path`，禁止 `../` 逃逸。
3. 在 Tool Registry 中注册只读文件工具。
4. 给每个工具设置清晰 JSON schema。
5. 为大文件设置简单最大字符数限制。
6. 写测试覆盖正常读取、找不到文件、路径逃逸。

## 完成标准
- agent 可以通过工具读取项目内文件。
- agent 不能读取项目外路径。
- 工具结果格式和错误格式稳定。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- 路径安全是否集中处理。
- 工具是否只读。
- 错误信息是否不会泄漏过多本机路径。

