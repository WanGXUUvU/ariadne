# TASK-020 - 会话上下文压缩

## 目标
为长会话补标准 compact 能力，参考 OpenAI/Codex 的 compact 思路，支持“主动压缩 + 自动压缩”两种触发方式，并由模型负责压缩会话中段的核心历史，再把 compact 结果接回后续 `/run`。

## 产品层
Context Management / Session

## 背景
现在 runtime 会把 `AgentState.messages` 里的历史消息继续带进后续请求。随着轮数增加、tool result 变长，prompt 会越来越大。OpenAI 官方做法不是只靠 context window，而是同时提供 compact 能力：当上下文变大后，先 compact，再继续后续请求。

当前任务不再走“本地规则摘要第一版”，而是直接对齐更标准的路线：
- 保留现有 `AgentState.messages` 作为上下文主结构
- 提供 `POST /compact` 作为主动压缩入口
- 在 `POST /run` 前按阈值自动触发 compact
- 两种入口共享同一套 compact 编排逻辑
- 调用大模型对会话中段做 summary/compact
- 保留前锚点消息和最近若干条原始消息
- compact 后继续复用压缩后的 `messages` 参与后续 `/run`

## 范围内
- 定义最小 compact 触发条件
  - 第一版可先按消息条数判断
  - 结构上为后续 token budget 触发留口
- 支持两种触发方式
  - 手动 `POST /compact`
  - 自动 `POST /run` 前检查并触发
- 提供共享的 compact 编排逻辑
  - 输入当前 `AgentState` 或其 `messages`
  - 识别前锚点 / 中段历史 / 最近原始消息
  - 调用 LLM 生成中段 compact summary
  - 输出 compact 后的新 `messages` / 新 `AgentState`
  - 返回 `did_compact` 等最小 metadata
- 压缩策略采用“三段式”
  - 保留前锚点消息
  - 压缩中段核心历史
  - 保留最近 N 条原始消息
- 生成一条明确标记为 compact summary 的特殊消息
- compact 后 session 仍可继续 `/run`
- 为手动/自动 compact 行为写测试

## 范围外
- 第一版就做精确 token 估算触发
- 自动后台 compact
- 多层摘要树
- 长期 memory 系统
- 人工编辑 summary
- 复杂 tool 输出语义重写
- 完整复刻 OpenAI `/responses/compact` 的 opaque/encrypted item 结构
- 直接依赖模型窗口内部实现细节

## 实现步骤
1. 明确 compact 的职责边界：
   - `route` 只负责入口
   - `service/runtime` 负责触发与编排
   - compact 核心逻辑负责切分消息并调用 LLM
   - `store` 负责保存 compact 后的新 state
2. 定义 compact 输入输出：
   - 输入：当前 `AgentState.messages`、阈值配置、锚点保留规则、保留最近消息数量
   - 输出：compact 后的 `messages`、`did_compact`、可选压缩统计
3. 定义三段式 compact 切分规则：
   - 前段：保留少量锚点消息，默认至少保留最初任务目标相关消息
   - 中段：交给 LLM 压缩为 1 条 compact summary
   - 后段：保留最近 N 条原始消息
4. 设计 compact prompt：
   - 明确要求模型保留任务目标、关键约束、重要工具结果、未完成事项
   - 明确要求模型不要伪装成逐字历史
   - 输出稳定、可重复消费的 summary 文本
5. 定义 compact summary message 格式：
   - 先复用现有 `ChatMessage`
   - 在 `content` 中明确标记这是 compact summary，不是原始逐字历史
   - 角色默认放 `system`，避免伪装成 assistant 原话
5. 新增主动压缩入口：
   - `POST /compact` 调用 compact 核心逻辑并保存结果
6. 在 `/run` 主链路接入自动 compact：
   - run 前检查是否超过阈值
   - 如超过，先 compact 并保存，再继续本次运行
7. 写测试确认：
   - 短会话不 compact
   - 手动 `POST /compact` 能压缩并持久化
   - 自动 compact 会在 `/run` 前触发
   - compact prompt 会收到中段消息而不是整段全量消息
   - 前锚点和最近原始消息会被保留
   - compact 后继续 `/run` 不报错

## 完成标准
- 长 session 不会无限增长原始消息上下文
- `POST /compact` 可手动触发压缩
- `/run` 可在必要时自动触发压缩
- compact summary 由 LLM 生成并进入后续 prompt
- 前锚点消息仍保留
- 最近若干条消息仍保留原文
- compact 后继续 `/run` 不会报错
- 行为稳定可测试

## 验证
- 构造长 session state，验证 compact 前后 `messages` 变化
- 验证 `POST /compact` 会返回并持久化 compact 后 state
- 验证自动 compact 会在 `/run` 前触发
- mock LLM compact 调用，验证只压中段历史
- 验证前锚点和最近原始消息未丢失
- 验证 compact 后再次 `/run` 仍能得到回复
- `python3 -m unittest backend.tests.test_agent -v`

## Review 检查点
- 主动 compact 和自动 compact 是否共用同一套核心逻辑
- compact summary 是否明确标记为压缩摘要，而不是伪装成原始消息
- LLM compact prompt 是否覆盖任务目标、关键约束、工具结果、未完成事项
- 锚点选择规则是否过度复杂，是否还能保持最小闭环
- 保留最近消息的数量是否足够支撑后续对话
- compact 是否会意外丢失关键用户约束或工具结果
- 当前实现是否为以后引入 token budget 和更接近官方 compaction item 的结构留出空间
