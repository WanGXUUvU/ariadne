# TASK-025 — 代码审查 Bug 修复（后端）

## 背景
TASK-024 前端全链路闭环完成后，对前后端做了两轮完整代码审查。
前端 Bug 已由工具自动修复（见下方"已修复"），剩余后端 Bug 需要手动修。

## 已修复（前端，本任务不需要再做）
| Bug | 文件 | 修了什么 |
|-----|------|----------|
| F1 | `useWorkspace.ts` | `resetSession` 删完后不再加载已删 session，改为清空选中 + 刷新列表 |
| F2 | `client.ts` / `index.ts` | `enableSkill`/`disableSkill` 返回类型从 `{status}` 改为 `SkillMetadata` |
| F3 | `client.ts` / `useWorkspace.ts` / `index.ts` | `compactSession` 返回类型从 `{status}` 改为 `CompactResponse`，去掉 `as any` |
| F5 | `types/index.ts` | `AgentMessage.content` 从 `string` 改为 `string \| null`，匹配后端 `Optional[str]` |
| F6 | `MessageList.vue` | 过滤掉 content 为空的 assistant 消息（tool_call-only），system 消息加 `?.` 防 null crash |
| F7 | `MessageList.vue` | `formatContent` 新增 markdown 表格解析，LLM 回复中的 `\| col \| col \|` 表格现在渲染成 HTML table |

## 待修（后端，按优先级排序）

### B1 🔴 `session_store.delete()` 内自行 commit，破坏事务一致性
- **文件**: `agent_prototype/storage/session_store.py` 第 128 行
- **问题**: `delete()` 内部自己做了 `db.commit()`，但调用方 `reset_session_service` 没有事务包裹。如果级联失败，service 层无法感知并 rollback。
- **修法**: 去掉 `delete()` 里的 `self.db.commit()`；在 `reset_session_service` 里加 `try/except` + `db.commit()` / `db.rollback()`。

### B2 🔴 `llm_client.py` HTTP 错误处理逻辑有问题
- **文件**: `agent_prototype/runtime/llm_client.py` 第 29-33 行
- **问题**: `if not response` 判断后才 `raise_for_status()`，且没有防御 `choices` 字段为空的情况。
- **修法**: 去掉 `if not response` 判断，直接 `response.raise_for_status()`；用 `data.get("choices")` 防御性读取并判空。

### B3 🟡 自动 compact 内部 commit 破坏外层事务
- **文件**: `agent_prototype/runtime/services.py` 第 206 行 + 第 150 行
- **问题**: `compact_session_service` 内部 `db.commit()` 了，但在 `run_agent_service` 自动 compact 路径中，如果后面 run 失败需要 rollback，compact 已经回滚不了。
- **修法**: 拆出一个 `_compact_in_memory()` 内部函数只做 state 计算不碰 DB commit；手动 compact 接口路径仍然正常 commit。

### B4 🟡 `upsert_session_snapshot` 无条件覆写 nullable 字段
- **文件**: `agent_prototype/storage/session_store.py` 第 59-62 行
- **问题**: `last_agent_name` / `last_skill_name` / `last_reply_preview` 每次更新都直接覆写，即使传的是 `None`。未来扩展时可能意外清空已有值。
- **修法**: 参考 `session_name` 的写法，只有非 None 时才覆写。

### B5 🟡 `search_text` 工具无深度/大小限制
- **文件**: `agent_prototype/tools_defs/fs_search.py` 第 17 行
- **问题**: `rglob("*")` 递归遍历整个目录树，模型如果传 `/` 或大目录会 OOM 或长时间卡住。
- **修法**: 加 `max_depth` 参数（默认 3 层）和 `max_results` 参数（默认 50 条），超限即停。

### B6 🟡 文件工具无路径限制（安全隐患）
- **文件**: `agent_prototype/tools_defs/fs_write.py` / `fs_read.py`
- **问题**: `write_file` / `read_file` 可以读写任意路径，模型可能意外操作系统文件。
- **修法**: 引入 `allowed_roots` 白名单或 `working_directory` 沙箱，默认只允许操作项目目录内的文件。

## Done 条件
- [ ] B1: `delete()` 去掉 commit，service 层统一事务
- [ ] B2: `llm_client` 错误处理修正
- [ ] B3: 自动 compact 路径不再提前 commit
- [ ] B4: upsert 字段覆写改为"非 None 才覆写"
- [ ] B5: `search_text` 加深度和结果数量限制
- [ ] B6: 文件工具加路径白名单限制
- [ ] 所有改动通过 `python3 -m unittest agent_prototype.tests.test_agent -v`

## 状态
- in-progress
