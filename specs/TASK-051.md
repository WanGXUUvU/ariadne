# TASK-051 - CLI 入口

## 目标
为编码产品提供命令行入口，让开发者可以在终端里和 Coding Agent 交互，不需要打开浏览器。

## 产品线
编码产品

## 范围内
- 在 `agent_prototype/cli/` 目录下实现入口
- 实现 `agent_prototype/cli/main.py`，支持交互式 REPL 模式
- 启动时显示当前 session_id、agent、workspace
- 支持 `/exit`、`/new`、`/status` 等基础 slash command
- 调用已有后端 API（不绕过 API，保持单一数据入口）
- 支持 `--agent` 参数指定 agent_name

## 范围外
- 离线运行（绕过 API）
- 复杂 TUI 界面
- 颜色主题配置
- 历史命令补全（可做占位）

## 实现步骤
1. 新建 `agent_prototype/cli/main.py`。
2. 实现启动参数解析：`--agent`、`--session`、`--workspace`。
3. 实现 REPL 主循环：读取输入 -> 调用 `POST /run` -> 打印 reply。
4. Streaming 模式：对接 `POST /run/stream`，逐字打印。
5. 实现 `/exit`、`/new`、`/status` slash command。
6. 工具调用发生时在终端显示 `[tool: xxx]` 标记。
7. 写基础启动测试（不依赖真实 API）。

## 完成标准
- 开发者可以 `python3 -m agent_prototype.cli.main --agent coding` 启动。
- 能正常对话并看到工具调用标记。
- `/exit` 优雅退出，不丢最后一条消息。

## 验证
- 手动启动 CLI，发送几条消息并触发工具调用。
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- CLI 是否只调用 API，不直接访问数据库。
- streaming 断流是否优雅处理。
- 是否避免把业务逻辑写进 CLI 主循环。
