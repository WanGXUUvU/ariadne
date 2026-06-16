# TASK-037 - Stop 按钮（截断保存）

## 目标
在对话界面加入 Stop 按钮，用户点击后立即停止流式输出，并将已输出的截断内容保存到会话状态，下次发消息时上下文连续。

## 产品层
Chat UI / Runtime

## 用户动作
用户在 agent 回复过程中点击 Stop 按钮。

## 用户会看到
- 流式文字立即停止
- 截断内容以完整消息形式保留在对话框（带"⏹ Stopped"标记）
- 下次发消息时，上下文包含这条截断回复

## 范围内
- 后端：新增 `POST /sessions/{session_id}/runs/{run_id}/finalize` 接口，接收截断内容并落库
- 后端：`session_store` 新增保存截断 run 的方法
- 前端：Stop 按钮（流式过程中显示，完成后隐藏）
- 前端：点 Stop → abort SSE → 调 finalize 接口保存截断内容
- 前端：截断消息 UI 标记（"⏹ Stopped"）

## 范围外
- 后端主动中断 LLM 调用（技术上做不到）
- 中断 tool call 执行
- server-side cancel 标记机制

## 实现步骤
1. 后端 `session_store` 加 `save_partial_run()` 方法
2. 后端新增 `finalize` 路由
3. 前端 `client.ts` 加 `finalizeRun` API
4. 前端 `useWorkspace.ts` 加 stop 状态和 `stopStreaming()` 方法
5. 前端 `ChatPanel.vue` 加 Stop 按钮，截断消息加"⏹ Stopped"标记
6. 测试 + 手动验证

## 完成标准
- 点 Stop 后流式停止，截断内容出现在对话框
- 刷新页面后截断内容仍然存在（已落库）
- 下次发消息时截断内容在 context 里

## 验证
- `python3 -m unittest discover -s backend/tests -p 'test_*.py' -v`
- 手动点 Stop，验证 UI 和数据库

## Review 检查点
- finalize 接口是否幂等（重复调用不出错）
- 截断内容是否正确写入 session state
- Stop 按钮是否只在 streaming 时显示
