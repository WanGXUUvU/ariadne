# TASK-017 - Skill 索引元数据

## 目标
扫描本地 skill，生成轻量索引，只暴露 name、description、path、enabled 等元数据。

## 产品层
Skill Management

## 范围内
- `list_skills()`
- 返回 skill name、description、path
- 标记 enabled 状态
- 处理格式错误 skill

## 范围外
- 加载完整 instructions
- 自动选择 skill
- 插件 marketplace

## 实现步骤
1. 在 loader 附近新增 index 函数。
2. 遍历 `.opencode/skills/*/SKILL.md`、`.agents/skills/*/SKILL.md` 以及全局技能目录。
3. 只读取 frontmatter metadata，不读取或不返回完整 instructions。
4. 对坏 skill 返回 disabled/error 状态。
5. 新增 API 或 service 测试。

## 完成标准
- 系统能列出所有本地 skill。
- 坏 skill 不会拖垮整个列表。
- 索引结果足够 UI 使用。

## 验证
- `python3 -m unittest backend.tests.test_agent -v`

## Review 检查点
- 是否符合渐进加载思路。
- 错误 skill 是否可见。
- path 是否不会泄漏过多本机信息。
