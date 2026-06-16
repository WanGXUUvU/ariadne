# TASK-033 - 配置层与项目信任

## 目标
按 Codex 官方配置分层思路，建立统一配置层，支持项目级配置、项目信任和 session 级覆盖。

## 产品层
Config / Runtime

## 背景
Codex 官方把用户级 `~/.codex/config.toml`、项目级 `.codex/config.toml`、项目 trust 状态和会话内临时覆盖分开处理。
当前项目只有零散的运行配置，还没有明确“哪些配置来自项目、什么时候允许加载项目配置、session 如何覆写”的边界。

## 范围内
- 新增统一配置对象
- 支持项目级 `.codex/config.toml` 最小加载
- 支持项目 trust 状态，未信任项目不加载项目级配置
- 支持 session 覆盖配置
- API 能读取当前 effective config
- 先覆盖 `model`、`personality`、`default agent`、`default skill`、`default_permissions`、`web_search`
- 预留 `/model`、`/personality`、`/agents`、`/skills`、`/permissions` 命令入口

## 范围外
- 企业级 `requirements.toml`
- 完整配置文件热加载
- 多用户配置同步
- UI 设置页

## 实现步骤
1. 新建 `config.py` 或 `runtime_config.py`。
2. 定义 default config 和项目级 config schema。
3. 增加项目 trust 状态，未信任项目跳过 `.codex/config.toml`。
4. 在 session metadata 中保存 overrides。
5. 实现 `get_effective_config(session_id)`，明确合并顺序。
6. 写测试确认默认值、项目配置和 session 覆盖合并正确。

## 完成标准
- 配置来源清晰，至少区分默认值、项目配置和 session 覆盖。
- 未信任项目不会自动注入项目级配置。
- session 可以覆盖少量配置。
- 现有运行链路能读取 model / personality / permissions 配置但行为不变。

## 验证
- `python3 -m unittest backend.tests.test_agent -v`

## Review 检查点
- 配置是否集中。
- trust 边界是否清楚。
- 是否避免环境变量、常量、session 状态多处混杂。
- 默认配置是否适合学习阶段。
