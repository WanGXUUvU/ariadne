# TASK-015 - Session 列表和读取接口

## 目标
提供最小 session 管理 API，让产品能展示已有会话。

## 产品层
产品表面层（Product Surface）

## 范围内
- 新增 `GET /sessions`
- 新增 `GET /sessions/{session_id}`
- 返回 session metadata 和 state 摘要
- 补 API 测试

## 范围外
- 分页
- 搜索
- 用户权限
- 前端 UI

## 完成标准
- 可以列出 session
- 可以读取单个 session
- 不影响 `/run` 和 `/reset`

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`
