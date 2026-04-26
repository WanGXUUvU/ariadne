# TASK-022 - 最小 CLI 入口

## 目标
提供一个最小命令行入口，方便像 Codex/Claude Code 一样从终端使用 agent。

## 产品层
产品表面层（Product Surface）

## 范围内
- 新增本地 CLI 脚本入口
- 支持输入 session_id、skill_name、user_input
- 打印干净 reply
- 可选打印 events

## 范围外
- 交互式 TUI
- 多行编辑器
- 自动补全
- 登录系统

## 完成标准
- 可以不启动浏览器直接运行 agent
- CLI 输出默认干净
- 调试模式能看到 trace

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`
- 手动运行一次 CLI
