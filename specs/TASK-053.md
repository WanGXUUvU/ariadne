# TASK-053 - Diff Viewer UI 面板

## 目标
在编码产品的 UI 中展示 agent 提议的文件修改 diff，支持用户确认应用或拒绝，形成"提议 → 审查 → 应用"的安全闭环。

## 产品线
编码产品

## 依赖
- TASK-045 文件写入草案与 diff 已完成
- TASK-043 工具审批流程已完成

## 范围内
- Trace 面板中识别 `file_change_proposed` 事件
- 展示 unified diff（旧内容红色，新内容绿色）
- 提供 Apply / Reject 按钮
- Apply 后调用后端应用 patch 接口
- 显示 apply 结果（成功/失败）
- 支持展开/折叠大 diff

## 范围外
- 三方合并界面
- 多文件批量 apply
- 行内编辑
- git commit 集成

## 实现步骤
1. 后端确认已有 apply patch 接口（如无则先补一个简单的 `POST /patches/{patch_id}/apply`）。
2. 前端在 Trace 面板增加 `DiffViewer` 组件。
3. 解析后端返回的 unified diff 字符串并渲染红绿色。
4. Apply 按钮调用后端接口，Reject 按钮标记为已拒绝。
5. 处理文件已被外部修改导致 patch 无法应用的错误。
6. 大 diff（超过 200 行）默认折叠。

## 完成标准
- 用户能清晰看到 agent 想改什么、改哪一行。
- Apply 后文件内容确实发生变化。
- Reject 后文件不被修改，trace 中有拒绝记录。

## 验证
- 手动触发一次文件修改提议，在 UI 中 Apply，确认文件内容变化。
- 手动 Reject，确认文件未修改。
- 前端构建命令通过。

## Review 检查点
- Apply 接口是否幂等（重复点击不会应用两次）。
- 错误提示是否清楚（patch 冲突、文件不存在等）。
- 是否避免在前端直接写文件（必须通过后端）。
