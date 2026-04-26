# TASK-013 - 工具结果规范化

## 目标
统一工具输出格式，避免每个工具随意返回不同结构，方便 trace 和前端展示。

## 产品层
工具注册层 + 执行轨迹层（Tool Registry + Execution Trace）

## 范围内
- 定义 `ToolResult`
- 支持 text/json 两类最小输出
- `AgentEvent` 使用规范化后的内容
- 保持传回模型的 tool message 可用

## 范围外
- 文件输出
- 图片输出
- 流式输出
- 大对象存储

## 完成标准
- 工具结果有统一结构
- `events` 和模型回填都能使用结果
- 现有 echo 工具行为不变

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`
