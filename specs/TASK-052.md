# TASK-052 - 权限审批界面

## 目标
为 `approval_required` 事件提供 UI 审批入口，让用户可以允许或拒绝高风险动作。

## 产品层
Frontend / Permission

## 范围内
- 显示待审批动作
- 展示 tool name、arguments、风险提示
- 提供 approve / reject 按钮
- 审批结果写回后端
- trace 中更新结果

## 范围外
- 多用户审批
- 企业策略
- 批量审批

## 实现步骤
1. 前端监听 run 返回的 approval 事件。
2. 实现 ApprovalPanel 或 modal。
3. 点击 approve/reject 调用后端 API。
4. 更新 session trace。
5. 处理审批已过期或已处理的状态。

## 完成标准
- 需要审批时用户能明确看到。
- 拒绝后动作不会执行。
- 允许后流程能继续或给出下一步提示。

## 验证
- 用一个设置为 `ask` 的工具手动验证。
- 前端构建命令通过。

## Review 检查点
- 风险信息是否足够清楚。
- approve/reject 是否幂等。
- UI 是否避免误点高风险动作。

