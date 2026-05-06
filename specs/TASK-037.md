# TASK-037 - Skill 草稿创建流程

## 目标
提供创建 skill 草稿的后端流程，让系统能生成一个可编辑的 `SKILL.md`。

## 产品层
Skill Authoring

## 范围内
- 新增 create skill draft 函数
- 输入 name、description、instructions
- 创建目录和 `SKILL.md`
- 防止覆盖已有 skill
- 基础名称校验

## 范围外
- 让 LLM 自动生成 skill
- UI 编辑器
- 插件打包

## 实现步骤
1. 定义 skill name 规则，只允许安全字符。
2. 实现目录创建。
3. 根据模板写入 `SKILL.md`。
4. 如果目录已存在，返回错误。
5. 写测试覆盖成功、重名、非法名称。

## 完成标准
- 可以创建一个新的本地 skill 草稿。
- 不会覆盖已有 skill。
- 新 skill 能被 `list_skills()` 发现。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- 文件名是否安全。
- 模板是否和 loader 格式一致。
- 是否避免自动生成过多复杂内容。
