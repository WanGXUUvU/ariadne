# TASK-027 - Responses API 迁移计划

## 目标
制定从当前 Chat Completions 风格迁移到 Responses API 的计划。

## 产品层
会话运行层（Session Runtime）

## 范围内
- 对比当前 adapter 和 Responses adapter 的输入输出
- 明确 tool call / tool output 映射
- 明确 session state 是否继续本地管理
- 创建迁移实施卡

## 范围外
- 直接迁移代码
- 删除现有 adapter
- 改 UI
- 改 SkillPack 格式

## 完成标准
- 迁移风险清楚
- 字段映射清楚
- 可以进入小步实现

## 验证
- 仅 Review
