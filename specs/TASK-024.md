# TASK-024 - Web UI 基础壳

## 目标
建立最小 Web UI：左侧 session 列表，中间对话区，右侧预留 trace/detail 区。

## 产品层
Frontend

## 范围内
- 选择前端技术栈并记录理由
- 实现基础布局
- 能创建或选择 session
- 能发送消息到 `/run`
- 能显示 assistant reply

## 范围外
- 完整设计系统
- trace 时间线
- skill 管理
- 权限审批弹窗

## 实现步骤
1. 确认前端目录，例如 `frontend/`。
2. 建立基础项目。
3. 封装 API client。
4. 实现 session sidebar。
5. 实现 chat input 和 message list。
6. 跑通一次真实 `/run`。

## 完成标准
- 用户不用 curl 也能和 agent 对话。
- session 切换不混乱。
- 移动端至少不崩。

## 验证
- 前端构建命令通过。
- 手动打开页面发送一条消息。

## Review 检查点
- UI 是否清楚区分 session 和 message。
- API 错误是否可见。
- 是否没有把业务逻辑都写进组件。

