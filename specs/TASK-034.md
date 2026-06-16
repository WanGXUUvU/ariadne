# TASK-034 - Token 与上下文使用统计

## 目标
记录每次运行的模型、输入输出 token、消息数量和耗时，让产品能显示运行成本和上下文压力。

## 产品层
Observability

## 范围内
- 在 model adapter 返回 usage 信息
- run record 保存 usage
- API 输出展示 usage summary
- 没有 usage 时允许为空

## 范围外
- 精确成本计算
- 多供应商价格表
- 自动截断

## 实现步骤
1. 扩展模型调用返回对象，加入 usage。
2. 从 OpenAI 返回中读取 token usage。
3. 写入 run record。
4. API 返回 `usage` 字段。
5. 测试 mock usage 能被保存。

## 完成标准
- 每次成功模型调用尽量记录 usage。
- usage 缺失不导致请求失败。
- 前端和 CLI 可以直接显示 usage。

## 验证
- `python3 -m unittest backend.tests.test_agent -v`

## Review 检查点
- usage 字段是否兼容不同模型供应商。
- 是否避免把统计逻辑散落在 agent 主循环。
- 是否清楚区分估算和官方返回。

