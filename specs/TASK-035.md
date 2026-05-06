# TASK-035 - Slash Command 解析器

## 目标
支持 `/status`、`/reset`、`/skills`、`/agents` 这类命令入口，为 CLI 和 UI 共用命令系统打基础。

## 产品层
Command Layer

## 背景
Codex CLI 有大量 slash commands。我们先做解析器和少量命令，不直接追求完整功能。

## 范围内
- 新建 command parser
- 支持识别普通用户输入和 slash command
- 实现 `/status`
- 统一已有 `/reset` 的语义
- 预留 `/skills`、`/agents`、`/model`、`/permissions`

## 范围外
- 复杂参数解析
- shell 命令
- UI 命令面板

## 实现步骤
1. 新建 `commands.py`。
2. 定义 `CommandResult` schema。
3. 解析以 `/` 开头的输入。
4. 在 service 层先分流 command 和 normal chat。
5. 给未知命令返回清晰错误。

## 完成标准
- 普通聊天不受影响。
- `/status` 能返回当前 session 基本状态。
- 未知命令不会进入 LLM。

## 验证
- 测试普通输入、已知命令、未知命令。
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- command 层是否独立于 FastAPI。
- 是否为 CLI/UI 复用预留结构。
- 是否避免把命令解析写死在路由里。
