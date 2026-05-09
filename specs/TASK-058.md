# TASK-058 - App / Connector 配置层

## 目标
对齐 Codex 官方 `apps` / `.app.json` 形态，定义本项目的 app 或 connector 配置模型和 metadata loader。

## 产品层
App / Connector Platform

## 依赖
- `TASK-057` Plugin 包结构对齐

## 范围内
- 定义 `.app.json` 的最小格式
- 定义 `apps.<id>` 的 enabled / approval / tool override 配置边界
- 读取插件里的 `.app.json`
- 建立 app metadata index
- 预留后续 app tools 进入 runtime 的接点

## 范围外
- 真正执行 connector 工具
- OAuth UI
- 第三方账号管理
- marketplace 发布

## 实现步骤
1. 定义 `.app.json` schema。
2. 定义 app 级和 tool 级 enable / approval metadata。
3. 读取插件 `.app.json` 并进入统一 app index。
4. 提供最小 API 或内部查询接口读取 app metadata。
5. 写测试覆盖坏格式、坏路径和禁用配置。

## 完成标准
- 插件里的 `.app.json` 可以被稳定读取。
- app 和 tool 级 metadata 边界清楚。
- 后续 app tool runtime 接入不需要重新改 manifest 结构。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- 是否与官方 `apps.<id>` 配置层对齐。
- 是否还没越界到真实 connector 执行。
- app 级和 tool 级配置是否分层明确。
