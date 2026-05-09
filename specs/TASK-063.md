# TASK-063 - Responses API 迁移计划

## 目标
制定从当前 Chat Completions 风格迁移到 Responses API 的计划。

## 产品层
Model Adapter / Runtime

## 背景
当前写法不是白写，它是 agent runtime 的基础。Responses API 迁移应该发生在 adapter 层，不能推翻 Skill、Tool、Session、Trace 的结构。

## 范围内
- 对比当前 adapter 和 Responses adapter 的输入输出
- 明确 tool call / tool output 映射
- 明确 session state 是否继续本地管理
- 创建迁移实施卡

## 范围外
- 直接迁移代码
- 删除现有 adapter
- 改 UI
- 改 skill / extension 格式

## 实现步骤
1. 列出当前 Chat Completions adapter 输入输出。
2. 阅读 Responses API 官方工具调用格式。
3. 写字段映射表：messages、instructions、tools、tool calls、tool outputs、usage。
4. 标记风险：streaming、state 管理、错误格式、测试 mock。
5. 根据映射结果拆出具体实现卡。

## 完成标准
- 迁移风险清楚。
- 字段映射清楚。
- 可以进入小步实现。

## 验证
- 仅 Review。

## Review 检查点
- 是否保留旧 adapter 作为回退。
- 是否避免一次性重写 runtime。
- 是否把迁移边界放在 model adapter 层。
