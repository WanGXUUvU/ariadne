# TASK-016 - Trace 回放接口

## 目标
把执行轨迹从一次响应里的临时数据，推进到可回放的产品能力。

## 产品层
执行轨迹层（Execution Trace）

## 范围内
- 设计 trace 存储位置
- 保存每次 `/run` 的事件序列
- 新增读取某次运行 trace 的接口
- 保持当前 response 仍然返回 events

## 范围外
- 实时流式事件
- 可视化时间线
- 长期压缩
- 分布式 trace

## 完成标准
- 用户可以在请求结束后再次读取 trace
- trace 和 session 能关联
- 当前测试和 API 行为不回退

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`
