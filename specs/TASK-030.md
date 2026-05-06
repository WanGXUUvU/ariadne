# TASK-030 - 权限配置数据结构

## 目标
建立最小权限模型，让系统能描述当前 agent 允许做什么，为后续工具审批、文件读写和命令执行打基础。

## 产品层
Permission / Safety

## 背景
Codex 类产品通常不会让 agent 无限制执行所有动作，而是通过 sandbox、approval policy、tool allowlist 等方式控制风险。本任务只做数据结构，不做真实拦截。

## 范围内
- 新增权限配置对象，例如 `PermissionProfile`
- 支持至少三个字段：`filesystem`、`network`、`shell`
- 支持简单等级：`deny`、`read_only`、`ask`、`allow`
- 给 session 保存当前 permission profile 名称
- 提供默认配置：学习阶段默认保守

## 范围外
- 真正阻止工具执行
- UI 审批弹窗
- 操作系统级 sandbox
- 多用户权限

## 实现步骤
1. 先在 `schemas.py` 定义权限相关 Pydantic schema。
2. 在 session state 或 session metadata 中保存当前 permission profile。
3. 在服务层给新 session 设置默认权限。
4. 暂时不改变任何工具行为，只让权限配置可以被读取。
5. 补一个单元测试，确认默认 session 有权限配置。

## 完成标准
- 权限配置可以随 session 保存和读取。
- 默认权限清晰，不依赖隐藏常量。
- 不影响现有 `/run`、`/reset` 行为。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- 权限 schema 是否过度复杂。
- 默认值是否保守。
- 是否把权限判断提前塞进太多地方。

