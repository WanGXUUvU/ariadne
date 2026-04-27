# TASK-036 - 运行配置与人格配置

## 目标
把 model、temperature、personality、default agent、default skill、permission profile 这类运行配置集中管理。

## 产品层
Config / Runtime

## 范围内
- 新增配置对象
- 支持项目级默认配置
- 支持 session 覆盖配置
- API 能读取当前 effective config
- 预留 `/model`、`/personality`、`/agents`、`/skills` 命令入口

## 范围外
- 完整配置文件热加载
- 多用户配置
- UI 设置页

## 实现步骤
1. 新建 `config.py` 或 `runtime_config.py`。
2. 定义 default config。
3. 在 session metadata 中保存 overrides。
4. 实现 `get_effective_config(session_id)`。
5. 写测试确认默认值和覆盖值合并正确。

## 完成标准
- 配置来源清晰。
- session 可以覆盖少量配置。
- 现有 LLM 调用能读取 model 配置但行为不变。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- 配置是否集中。
- 是否避免环境变量、常量、session 状态多处混杂。
- 默认配置是否适合学习阶段。
