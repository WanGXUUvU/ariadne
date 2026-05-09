# TASK-047 - Git diff 读取能力

## 目标
让系统能读取当前工作区 diff，为 Review 模式和用户确认改动打基础。

## 产品层
Git / Review

## 范围内
- 新增 git service
- 读取 `git status --short`
- 读取 `git diff`
- 读取 staged diff
- 提供 API 或工具输出

## 范围外
- 自动 commit
- 自动 push
- 冲突解决

## 实现步骤
1. 新建 `git_service.py`。
2. 用 subprocess 非交互调用 git。
3. 设置超时和最大输出长度。
4. 在 API 中暴露 status 和 diff。
5. 写测试时 mock subprocess。

## 完成标准
- 用户能看到当前改动摘要。
- 大 diff 不会无限输出。
- git 不可用时返回清晰错误。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- 是否避免 destructive git 命令。
- subprocess 是否有超时。
- 输出截断是否可解释。

