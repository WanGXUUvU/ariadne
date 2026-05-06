# TASK-033 - 文件写入草案与 diff

## 目标
让 agent 可以提出文件修改草案，但默认不直接写入，先生成 diff 供用户审查。

## 产品层
Workspace / Review

## 背景
真实代码 agent 需要能改文件，但学习阶段应该先建立“计划、diff、审批、应用”的安全闭环。

## 范围内
- 新增 `propose_file_change` 工具
- 输入包含目标文件路径和新内容
- 系统生成 unified diff
- diff 作为 trace 事件返回
- 保存待应用的 patch 草案

## 范围外
- 自动应用 patch
- 复杂三方合并
- git commit
- UI diff viewer

## 实现步骤
1. 新增 patch proposal schema。
2. 读取旧文件内容并和新内容生成 diff。
3. 把 proposal 保存到 session 关联状态。
4. 新增 trace 事件 `file_change_proposed`。
5. 写测试确认不会直接改文件。

## 完成标准
- 工具调用后磁盘文件不变。
- API 返回可读 diff。
- proposal 可以被后续任务读取。

## 验证
- 测试前后读取文件内容，确认没有被修改。
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- 是否把“生成 diff”和“应用修改”严格分开。
- proposal 是否包含足够上下文。
- 大文件 diff 是否有基础限制。

