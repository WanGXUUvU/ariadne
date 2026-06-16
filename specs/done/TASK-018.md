# TASK-018 - 渐进式 Skill 加载

## 目标
模拟 OpenCode 式的渐进式加载：初始只给模型 skill 摘要，只有选中时才加载完整 instructions。

## 产品层
Skill Management / Context

## 范围内
- 构造 skill catalog prompt
- 初始 prompt 只包含 name/description
- 显式选中后加载完整 `SKILL.md`
- 限制 catalog 长度

## 范围外
- 自动智能选择
- 8,000 字符预算的完整实现
- 多 skill 同时加载

## 实现步骤
1. 用 `list_skills()` 得到摘要。
2. 写 `build_skill_catalog_prompt()`。
3. 在 prompt 构造中区分 catalog 和 selected skill instructions。
4. 设置最大 skill 数量或最大字符数。
5. 测试 catalog 不包含完整 instructions。

## 完成标准
- 有很多 skill 时不会全部塞进上下文。
- 被选中 skill 才加载完整内容。
- 行为可测试。

## 验证
- `python3 -m unittest backend.tests.test_agent -v`

## Review 检查点
- 是否真正减少上下文。
- catalog 是否足够模型选择。
- 超长 description 是否会被截断。
