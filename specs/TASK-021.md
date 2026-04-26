# TASK-021 - API 输出整理

## 目标
把 API 输出整理成更适合产品使用的稳定结构。

## 产品层
产品表面层（Product Surface）

## 范围内
- 明确用户可见 reply 和内部 trace 的边界
- 统一错误响应格式
- 返回当前 session、skill、run metadata
- 更新测试快照

## 范围外
- 前端 UI
- 流式输出
- 鉴权
- 国际化

## 完成标准
- `/run` 输出能直接支撑 UI
- 错误格式稳定
- 现有行为有兼容方案

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`
