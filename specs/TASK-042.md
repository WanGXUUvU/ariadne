# TASK-042 - 权限配置与 Sandbox Profile

## 目标
建立与 Codex 官方更接近的权限配置模型，先描述 sandbox mode、approval policy 和 named permission profile，再给后续审批与工具执行打基础。

## 产品层
Permission / Safety

## 背景
Codex 官方把安全边界拆成两层：`sandbox mode` 负责技术边界，`approval policy` 负责什么时候停下来问用户。
当前项目原本只想建一个简单 `PermissionProfile`，但如果要贴近官方，第一版就应该把 `sandbox_mode`、`approval_policy`、`default_permissions` 和命名 profile 的关系说明白。

## 范围内
- 新增权限配置对象，例如 `PermissionProfile`
- 支持 `sandbox_mode`：`read-only`、`workspace-write`、`danger-full-access`
- 支持 `approval_policy`：`untrusted`、`on-request`、`never`
- 支持 named permission profiles 的最小模型
- 支持 filesystem / network 的最小配置
- 给 session 保存当前 permission profile 名称
- 提供默认配置：学习阶段默认保守

## 范围外
- 真正阻止工具执行
- UI 审批弹窗
- 操作系统级 sandbox
- 复杂规则系统
- 多用户权限

## 实现步骤
1. 先在 `schemas.py` 定义权限相关 Pydantic schema。
2. 定义默认 `sandbox_mode`、`approval_policy` 和 `default_permissions`。
3. 在 session state 或 session metadata 中保存当前 permission profile。
4. 在服务层给新 session 设置默认权限。
5. 暂时不改变任何工具行为，只让权限配置可以被读取。
6. 补一个单元测试，确认默认 session 有权限配置。

## 完成标准
- 权限配置可以随 session 保存和读取。
- 默认权限清晰，不依赖隐藏常量。
- 至少能表达 sandbox、approval 和 named profile 三层信息。
- 不影响现有 `/run`、`/reset` 行为。

## 验证
- `python3 -m unittest backend.tests.test_agent -v`

## Review 检查点
- 权限 schema 是否过度复杂。
- 默认值是否保守。
- 是否与后续审批流有清晰边界。
- 是否把权限判断提前塞进太多地方。
