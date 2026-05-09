# TASK-035 - Web 搜索工具

## 目标
为聊天助理添加网络搜索能力，让 agent 在需要最新信息时可以主动调用搜索，而不是依靠训练知识。

## 产品线
聊天助理

## 范围内
- 新增 `web_search` 工具定义
- 接入一个搜索 API（优先 SerpAPI 或 Tavily，可配置）
- 返回摘要列表（title、url、snippet），限制数量
- 工具结果写入 trace
- API Key 通过环境变量读取，不硬编码

## 范围外
- 自建爬虫
- 图片搜索
- 搜索结果缓存
- 完整网页抓取

## 实现步骤
1. 在 `tools_defs/` 新建 `web_search.py`。
2. 定义 JSON schema：`query`（必填）、`num_results`（可选，默认 5）。
3. 实现搜索 API 调用，读取环境变量 API Key。
4. 返回 `ToolResult`，内容为搜索结果摘要列表。
5. 在 Tool Registry 注册。
6. 在 assistant agent 定义的 tool_names 中加入 `web_search`。
7. 写测试 mock HTTP 调用，不依赖真实网络。

## 完成标准
- assistant agent 在需要时能主动搜索并引用结果。
- API Key 缺失时返回清晰错误，不崩溃。
- 搜索结果数量有上限，不会撑爆上下文。

## 验证
- `python3 -m unittest agent_prototype.tests.test_agent -v`
- 手动问一个需要最新信息的问题，观察工具调用。

## Review 检查点
- API Key 是否只从环境变量读取。
- 搜索结果是否有字数/条数限制。
- 搜索失败是否返回 `tool_error` 而不是崩溃。
