# TASK-094C: 工具状态语义拆分 (Tool State Semantics)

## 1. 这张卡的范围

TASK-094 原始卡被拆为三张：
- **094A** ✅ — 统一 Run 终态收口（`RunPersistenceService.finalize_run()`）
- **094B** ✅ — RunExecutionSession 通用化，StreamRunSession 收窄为 SSE 适配层
- **094C** ← 本卡 — 工具层语义：staged/committed/rolled_back 状态拆分 + RPC 终态 FAILED 接入 + 写工具返回去自然语言化

---

## 2. 设计原则（参考 Claude Code 工具设计）

Claude Code 的工具设计有一条核心假设：**内容通道 = 唯一的真相源**。模型和前端看的是同一份内容，不存在"这份给模型、那份给前端"的分叉。具体而言：

1. **不设 `ok` 字段**。成功/失败从内容本身判断，不靠布尔值承载。模型读内容就知道发生了什么。
2. **紧凑是工具的自然形状，不是刻意设计的协议层**。`cat -n` 格式、原始输出都是工具自然产出的，不需要发明一套新协议语言。
3. **`read_file` 返回数据本体**。模型需要看到文件内容才能工作——这不是状态消息，不能压缩。
4. **写工具的返回只承载"做了什么"的确认**。够了。不需要教模型 file system 的工作原理。

---

## 3. 当前问题

1. **写工具返回啰嗦**：`"Staged 128 chars to /path/src/a.py (not yet committed)"` — 自然语言句子浪费 token，信息密度低。
2. **模型不知道写操作是暂存还是已落盘**：`ok=True` 同时承载"执行成功"和"已落盘"，但 staged 场景下文件还没真正写盘。
3. **`stream_run_session.py` 异常路径没接 FAILED**：网络/流式异常只 log + re-raise，没调 `finalize_run(status=FAILED)` 落库。
4. **DB + VFS 非原子**：先 `db.commit()` 后 `vfs.commit_all()`，崩溃场景不保证一致性。本次不强制落地，记录升级路径即可。

---

## 4. 方案设计

### 4.1 ToolState 枚举（metadata 里塞）

```python
class ToolState(str, Enum):
    STAGED = "staged"          # 工具执行成功，仅进入 run VFS
    COMMITTED = "committed"    # run 完成，VFS 已落盘
    ROLLED_BACK = "rolled_back"  # run 取消/失败，VFS 已丢弃
```

`ToolResult` 已有 `metadata: dict[str, Any]` 字段，直接往里填 `state` / `path` / `bytes`：

```python
ToolResult(
    ok=True,
    content="wrote src/a.py  128B",          # 给模型：紧凑确认
    metadata={
        "state": "staged",
        "path": "src/a.py",
        "bytes": 128,
    },
)
```

**不需要 `display_text`**。前端读 `metadata.state` 枚举值自己生成 UI 文案——保持单一真相源。

### 4.2 各工具返回策略

| 工具 | 改不改 | 理由 |
|------|--------|------|
| `write_file` | **改** — 紧凑确认格式 | 返回的是状态确认，不是数据。模型只需要知道"写了什么、写了多少" |
| `read_file` | **不动** | 返回的是数据本体。模型需要读内容才能写代码，压缩等于自毁 |
| `search_text` | **不动** | 同上，返回搜索结果数据 |
| `list_dir` | **不动** | 同上，返回目录列表数据 |

`write_file` 返回格式从：
```
Staged 128 chars to /workspace/src/a.py (not yet committed)
```
改为：
```
wrote src/a.py  128B
```

`wrote` 这个词本身就是"暂存已写入"的意思——模型不需要知道 VFS 的存在。如果 run 取消了，模型根本不会看到这次调用的结果（因为 run 没完成，不会进入下一轮上下文）。

### 4.3 staged → committed / rolled_back 转换

这个转换发生在 `RunPersistenceService.finalize_run()` 里，不和工具层耦合：

- run **completed** → VFS `commit_all()` → 所有工具的 staged 写入变成 committed
- run **cancelled / failed** → VFS `discard()` → 所有工具的 staged 写入变成 rolled_back

前端怎么知道？**SSE `end` 帧已经带了 run status**，前端根据 status 推断工具最终状态即可。不需要额外通信通道。

### 4.4 异常路径接 FAILED

`StreamRunSession.run()` 当前：

```python
except Exception:
    logger.exception(...)
    raise        # ← 只记日志，没落库
```

改为在 re-raise 前调 `persist.finalize_run(status=FAILED)`：

```python
except Exception:
    logger.exception(...)
    self.persist.finalize_run(RunFinalizationInput(
        session_id=self.agent_input.session_id,
        run_id=self.run_id,
        status=RunFinalStatus.FAILED,
        user_input=self.agent_input.user_input,
        partial_reply="",
        events=[],
    ))
    raise
```

### 4.5 DB/VFS 原子性（记录，不落地）

当前接受非原子。升级路径记录：
1. 增加 `finalizing` 中间态
2. 或引入可恢复 commit log
3. 或两阶段收口协议

代码结构已预留扩展点：`_apply_vfs_terminal_action` 是独立方法，后续加中间态或 WAL 不触及其他逻辑。

---

## 5. 用户可见效果

- 写工具返回从一行英文句子变成紧凑确认行
- 工具卡片根据 run 终态显示不同状态（工具执行时都是 staged；run 结束后根据 completed/cancelled/failed 推断最终状态）
- 网络异常时 run 正确标记为 `failed`，不再和用户取消混在一起

---

## 6. 涉及文件

| 层 | 文件 | 改动 |
|----|------|------|
| 工具结果 | `tools/result_types.py` | 新增 `ToolState` 枚举 |
| 文件工具 | `tools/builtin/filesystem/fs_write.py` | 返回紧凑确认 + 填充 `metadata` |
| SSE 适配 | `execution/streaming/stream_run_session.py` | except 块调 `finalize_run(FAILED)` |
| 前端 | 工具卡片组件 | 读 `metadata.state` 渲染状态徽章 |

---

## 7. 完成标准

- `ToolResult.metadata` 包含 `state` / `path` / `bytes`
- `fs_write.py` 返回紧凑确认格式
- `stream_run_session.py` 异常路径接入 FAILED 终态
- 前端工具卡片根据 metadata.state 区分 staged / committed / rolled_back
- 现有测试全绿

## 8. 验证

```bash
python3 -m unittest discover -s agent_prototype/tests -p 'test_*.py' -v
cd frontend && npm run build
```
