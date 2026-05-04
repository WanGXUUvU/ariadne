# TASK-020 - 会话上下文压缩

## 目标
为长会话补最小 compact 能力：把较旧的消息压缩成一条 summary，减少后续 `/run` 的 prompt 压力，同时保留最近几轮原始消息。

## 产品层
Context Management / Session

## 背景
现在 runtime 会把 session state 里的历史消息继续带进后续请求。随着轮数增加、工具结果变长，prompt 会越来越大。我们已经对 skill 做了渐进加载，下一步需要对会话历史本身做压缩。

## 范围内
- 定义最小 compact 触发条件，第一版按消息条数判断
- 只压缩较旧的 user / assistant / tool 消息
- 生成一条明确标记为 summary 的消息
- 用 summary 替换旧历史，保留最近 N 条原始消息
- compact 后 session 仍可继续 `/run`
- 为 compact 行为写测试

## 范围外
- 精确 token 估算触发
- 自动后台 compact
- 多层摘要树
- 长期 memory 系统
- 人工编辑 summary
- 复杂 tool 输出语义重写

## 实现步骤
1. 定义 compact 策略：超过阈值时，仅保留最近 N 条原始消息。
2. 新增 `build_compact_summary(...)`，先用规则摘要生成旧上下文概览。
3. 定义 summary message 格式，明确告诉模型这是压缩摘要，不是原始逐字历史。
4. 在 runtime 或 service 层接入 compact 流程，把旧消息替换成 summary + 最近消息。
5. 保存 compact 后的新 session state。
6. 写测试确认：短会话不 compact，长会话会 compact，compact 后仍能继续运行。

## 完成标准
- 长 session 不会无限增长原始消息上下文。
- summary 会进入后续 prompt。
- 最近若干条消息仍保留原文。
- compact 后继续 `/run` 不会报错。
- 行为稳定可测试。

## 验证
- 构造长 session state，验证 compact 前后消息数量变化。
- 验证 compact 后再次 `/run` 仍能得到回复。
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- summary 是否明确标记为摘要，而不是伪装成原始消息。
- 保留最近消息的数量是否足够支撑后续对话。
- 是否先用“消息条数阈值”做最小闭环，避免过早引入 token 复杂度。
- compact 是否会意外丢失关键用户约束或工具结果。
