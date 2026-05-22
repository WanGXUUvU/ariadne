# TASK-072a — 模型选择平台：后端数据库 + API + 思考参数注入

## 背景

当前系统模型固定写在 `run_service.py` 的 `RUN_MODEL` 环境变量里，不支持多 Provider 管理、
模型选择和思考模式控制。本卡实现后端全链路：Provider 配置持久化 → 模型列表同步 →
session 绑定选择 → run_service 动态注入 thinking 参数。

同步实现 token-aware 压缩：利用 API 返回的 `usage.prompt_tokens` 替换原来按条数触发的压缩判断。

---

## 用户动作

用户在设置页填写 Provider（base_url + api_key）→ 后端保存 → 用户点"同步模型" → 后端转发
到 `{base_url}/v1/models` 拉取列表 → 用户勾选模型 → 对话框里出现该模型 → 用户选模型、开
启 thinking、选 effort → 前端存到 session → run 时用对应参数调用模型。

## 用户会看到

- 设置页中可新增 / 删除 Provider，可同步模型列表，可勾选哪些模型出现在对话框
- 对话框里的模型选择来自真实数据，而非硬编码

---

## 需要改的层

### 1. 数据库 migration（alembic）

新增两张表：

**`provider_configs`**
```
id          INTEGER  PK AUTOINCREMENT
name        TEXT     NOT NULL           -- 显示名，如 "SenseNova"
base_url    TEXT     NOT NULL           -- 如 "https://token.sensenova.cn/v1"
api_key     TEXT     NOT NULL           -- 加密存储（当前阶段明文，后续可扩展）
created_at  DATETIME DEFAULT NOW
```

**`model_settings`**
```
id               INTEGER  PK AUTOINCREMENT
provider_id      INTEGER  FK → provider_configs.id
model_id         TEXT     NOT NULL       -- 原始 model id，如 "deepseek-v4-flash"
display_name     TEXT                    -- 展示用名，可覆盖
enabled          BOOLEAN  DEFAULT FALSE  -- 是否出现在对话框
supports_thinking BOOLEAN DEFAULT FALSE  -- 从 supported_features 判断
thinking_style   TEXT                    -- "deepseek_style" | "sensenova_style" | "none"
effort_levels    TEXT                    -- JSON 数组，如 '["low","high"]'
context_length   INTEGER                 -- 从 /v1/models 读取
supports_tools   BOOLEAN DEFAULT FALSE
created_at       DATETIME DEFAULT NOW
UNIQUE(provider_id, model_id)
```

`session_records` 新增三列：
```
model_provider_id  INTEGER  FK → provider_configs.id（可 NULL，表示用默认环境变量）
model_id           TEXT     NULL
thinking_enabled   BOOLEAN  DEFAULT FALSE
thinking_effort    TEXT     DEFAULT "medium"
```

### 2. 新建文件 `agent_prototype/model/thinking_styles.py`

```python
THINKING_STYLES = {
    "deepseek_style": {
        "enable_payload": {"thinking": {"type": "enabled", "reasoning_effort": "{effort}"}},
        "disable_payload": {"thinking": {"type": "disabled"}},
        "effort_levels": ["low", "high"],
        "default_effort": "high",
    },
    "sensenova_style": {
        "enable_payload": {"reasoning_effort": "{effort}"},
        "disable_payload": {"reasoning_effort": "none"},
        "effort_levels": ["low", "medium", "high"],
        "default_effort": "medium",
    },
    "none": {
        "effort_levels": [],
    },
}

def build_thinking_payload(style: str, enabled: bool, effort: str) -> dict:
    """返回需要合并进请求 body 的 thinking 相关参数。"""
    ...
```

`{effort}` 占位符在 `build_thinking_payload` 里做字符串替换。

### 3. 后端 API（新增路由文件 `api/routes/settings.py`）

```
POST /settings/providers
    body: { name, base_url, api_key }
    → 写 provider_configs，返回 id

GET  /settings/providers
    → 列出所有 provider（api_key 脱敏，只返回 **** 后4位）

DELETE /settings/providers/{id}
    → 删除 provider 及其 model_settings（cascade）

GET  /settings/providers/{id}/models
    → 后端用 provider 的 base_url + api_key 请求 {base_url}/v1/models
    → 解析 supported_features，判断 supports_thinking、thinking_style
    → 写 / 更新 model_settings（upsert by provider_id+model_id）
    → 过滤掉 output_modalities 含 "image" 的模型（不是对话模型）
    → 返回模型列表（含 thinking_style、effort_levels）

PATCH /settings/models/{model_id_or_db_id}
    body: { enabled?, display_name? }
    → 更新 model_settings 对应字段
```

**thinking_style 推断规则**（在 settings.py 里内联）：
```python
def infer_thinking_style(model_id: str, features: list[str]) -> str:
    if "reasoning" not in features:
        return "none"
    if "deepseek" in model_id.lower():
        return "deepseek_style"
    return "sensenova_style"   # 默认商汤风格
```

### 4. 修改 `application/run_service.py`

在每次调用模型后：
```python
resp = adapter.generate(request)   # 或 stream
if resp.usage and resp.usage.input_tokens:
    session_store.update_context_tokens(session_id, resp.usage.input_tokens)
```

在构建 `ModelRequest` 前，读取 session 的 model_config 动态选模型和注入 thinking 参数：
```python
model_id = session.model_id or RUN_MODEL
thinking_payload = {}
if session.thinking_enabled and session.model_id:
    ms = model_settings_store.get(session.model_id)
    thinking_payload = build_thinking_payload(
        ms.thinking_style, True, session.thinking_effort
    )
adapter = ChatCompletionsAdapter(model=model_id, extra_body=thinking_payload)
```

### 5. 修改 `application/compact_service.py`

```python
# 修改前
if len(state.messages) <= trigger_threshold:

# 修改后（trigger_threshold 语义从"条数"改为"token 数"）
context_tokens = state.context_tokens or 0
if context_tokens < trigger_threshold:
```

`AgentState` / `CompactInput` 需新增 `context_tokens: int = 0` 字段。
`run_service` 调用 compact 前把最新 `context_tokens` 传入。
默认 `trigger_threshold` 从 `12`（条数）改为 `80000`（tokens）。

### 6. 注册路由

`api/app.py` 里 include settings router。

---

## Done Conditions

- [ ] alembic migration 可运行，三张表正确创建
- [ ] POST /settings/providers 能保存 provider
- [ ] GET /settings/providers/{id}/models 能拉取模型列表并写 model_settings
- [ ] PATCH /settings/models/{id} 能切换 enabled
- [ ] run_service 读 session.model_id，有值时用 session 指定的模型，无值回落到 RUN_MODEL
- [ ] run_service 读 session.thinking_enabled，按 thinking_style 注入正确参数
- [ ] run_service 每轮把 usage.input_tokens 存进 session（context_tokens）
- [ ] compact_service 用 context_tokens 判断是否压缩（阈值 80000）
