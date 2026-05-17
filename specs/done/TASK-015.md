# TASK-015 - Session 列表和读取接口

## 目标
提供产品层 session API，让用户可以查看历史会话并恢复某个会话。

## 产品层
API / Session

## 范围内
- `GET /sessions`
- `GET /sessions/{session_id}`
- 返回 metadata 和必要 state summary
- 支持按 updated_at 倒序

## 范围外
- 搜索
- 分页高级参数
- 删除 session

## 实现步骤
1. 在 session store 增加 list/read 方法。
2. 新增 response schema。
3. 新增 FastAPI routes。
4. 列表只返回摘要，不返回完整 messages。
5. 详情接口返回可恢复会话所需信息。
6. 写 API 或 service 测试。

## 完成标准
- 能列出历史 session。
- 能读取单个 session。
- 不存在的 session 返回 404 风格错误。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`

## Review 检查点
- 列表接口是否避免返回过大 state。
- 排序是否稳定。
- API 字段是否适合前端直接使用。

