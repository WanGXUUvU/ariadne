# TASK-042 - Review 模式

## 目标
实现一个专门审查代码变更的模式，优先找 bug、回归风险和缺失测试，而不是泛泛总结。

## 产品层
Review / Agent Behavior

## 范围内
- 新增 review agent 或 review mode
- 读取 git diff
- 生成 review prompt
- 输出 findings、questions、testing gaps
- 不自动修改代码

## 范围外
- 自动修复
- PR 评论机器人
- 多文件复杂静态分析

## 实现步骤
1. 定义 review mode 的输出格式。
2. 将 git diff 作为上下文输入。
3. 增加 `/review` command。
4. 如果采用 skill 形态，则只把它当作可选 review skill，不作为系统核心。
5. 测试 command 不会进入普通聊天路径。

## 完成标准
- `/review` 能基于 diff 输出审查结果。
- 没有 diff 时返回“无可审查改动”。
- 输出优先列问题，不先夸代码。

## 验证
- 用一个 mock diff 测试 review 输入构造。
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- review prompt 是否具体。
- 是否避免自动修改文件。
- 输出是否适合用户直接阅读。
