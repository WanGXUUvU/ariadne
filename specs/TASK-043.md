# TASK-043 - 工具审批流程

## 目标
在工具执行前加入最小审批状态，让高风险工具可以先返回“需要审批”，而不是直接执行。

## 产品层
Permission / Tool Runtime

## 背景
Codex 类产品会区分自动允许、需要确认、拒绝执行。本任务先实现后端状态流，不做 UI。

## 范围内
- 为 tool call 增加审批判断入口
- 当权限为 `ask` 时，返回 `approval_required` 事件
- 保存待审批 tool call 的基本信息
- 提供一个最小 API 用于 approve / reject
- approve 后允许继续执行对应工具

## 范围外
- 前端审批界面
- shell 工具
- 文件写入工具
- 多轮复杂恢复

## 实现步骤
1. 在事件 schema 中新增 `approval_required` 和 `approval_result` 类型。
2. 新增 pending approval 数据结构，记录 `session_id`、`tool_name`、`arguments`、`status`。
3. 在 tool runtime 执行前检查权限。
4. 如果需要审批，不执行工具，只保存 pending 状态并返回事件。
5. 新增 approve/reject API，先用最小实现跑通状态变化。

## 完成标准
- 需要审批的工具不会被直接执行。
- 审批状态可以被查询。
- 拒绝后 trace 中能看到拒绝事件。

## 验证
- 单元测试覆盖 allow / ask / deny 三种路径。
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- pending approval 是否能和 session 对齐。
- reject 后是否不会继续执行工具。
- 是否为后续 UI 留出清晰字段。

