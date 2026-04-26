# TASK-008 - 将 SkillPack 注入 Agent Runtime

## 目标
让 `Agent` 运行时使用从 SkillPack 加载出来的 instructions，而不是依赖单一硬编码 system prompt。

## 产品层
会话运行层（Session Runtime）

## 范围内
- 让 `Agent` 接收已加载的 SkillPack 文本
- 用 SkillPack instructions 生成 system prompt
- 保持 state 里不持久化 system message
- 补测试确认模型收到的 system prompt 来自 SkillPack

## 范围外
- 多 skill 自动选择
- 工具白名单
- Prompt 模板引擎
- Responses API 迁移

## 完成标准
- 默认 SkillPack 可以驱动一次完整 `/run`
- 现有工具调用闭环不受影响
- 测试能证明 system prompt 不再只来自硬编码常量

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`
