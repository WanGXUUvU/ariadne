# TASK-025 - Trace 时间线面板

## 目标
在 UI 中展示 agent 的执行轨迹：assistant tool call、tool result、final answer、error、approval。

## 产品层
Frontend / Trace

## 范围内
- 读取 `/trace` 或 `/run` 返回的 events
- 右侧显示时间线
- 不同事件类型有不同视觉区分
- 工具参数和结果可以展开查看

## 范围外
- 实时 streaming
- 图形化 DAG
- 高级过滤器

## 实现步骤
1. 定义前端 Event 类型。
2. 实现 TracePanel。
3. 按事件类型渲染不同块。
4. 长内容默认折叠。
5. 给空状态和错误状态做基本处理。

## 完成标准
- 用户能看懂 agent 为什么给出最终回答。
- 工具调用链路可追踪。
- 长内容不会把页面撑爆。

## 验证
- 用包含 tool call 的 session 手动验证。
- 前端构建命令通过。

## Review 检查点
- 时间线是否和后端 event schema 对齐。
- 是否保留原始调试信息入口。
- 是否避免 UI 过度复杂。

