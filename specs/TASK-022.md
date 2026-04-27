# TASK-022 - 最小 CLI 入口

## 目标
提供一个最小命令行入口，可以发送消息、指定 session、指定 agent，必要时指定 skill。

## 产品层
CLI

## 范围内
- 新增 `python -m agent_prototype.cli`
- 参数：message、session-id、agent-name、skill-name
- 打印 reply
- 可选打印 events
- 复用 service 层，不直接调 FastAPI

## 范围外
- 交互式 TUI
- slash command 全集
- 彩色复杂输出

## 实现步骤
1. 新建 `cli.py`。
2. 用 argparse 定义参数。
3. 调用现有 service。
4. 默认只打印最终回答。
5. `--events` 时打印结构化事件摘要。
6. 写最小测试或手动验证命令。

## 完成标准
- 不启动 HTTP 服务也能运行 agent。
- CLI 和 API 行为一致。
- 参数错误有清晰提示。

## 验证
- `python -m agent_prototype.cli "hello" --session-id cli-test`
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- CLI 是否没有复制业务逻辑。
- 输出是否适合人读。
- 是否不强依赖真实 API Key 测试。
