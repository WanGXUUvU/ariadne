# TASK-072b — 模型选择平台：前端设置页 + 对话框 ModelSelector

## 背景

TASK-072a 完成后端数据库和 API，本卡在前端实现两处 UI：
1. 设置页：Provider 管理 + 模型列表同步 + 模型勾选
2. 对话框：模型选择器 + thinking 开关 + effort 档位选择

依赖：TASK-072a 必须先完成。

---

## 用户动作与可见结果

| 动作 | 可见结果 |
|------|---------|
| 点击设置按钮，进入设置页 | 显示 Provider 列表面板 |
| 填写 name/base_url/api_key，点保存 | Provider 出现在列表 |
| 点"同步模型"按钮 | 该 Provider 下的模型列表展开，每行有启用开关 |
| 打开对话框 | ModelSelector 下拉显示所有 enabled=true 的模型 |
| 选择支持 thinking 的模型 | 出现 [思考] 开关 |
| 打开思考开关 | 出现 effort 档位选择（低/中/高，按模型支持的档位渲染） |
| 开始对话 | 后端用选择的模型+thinking 参数发请求 |

---

## 新增 / 修改文件

### 1. `frontend/src/api/settings.ts`（新建）

封装设置页所需的 API 调用：

```typescript
export interface Provider {
  id: number
  name: string
  base_url: string
  api_key_hint: string   // 脱敏后的 key，如 "****abcd"
}

export interface ModelSetting {
  id: number
  provider_id: number
  model_id: string
  display_name: string
  enabled: boolean
  supports_thinking: boolean
  thinking_style: string
  effort_levels: string[]   // ["low","high"] 等
  context_length: number
}

export const settingsApi = {
  listProviders(): Promise<Provider[]>
  createProvider(data: { name: string; base_url: string; api_key: string }): Promise<Provider>
  deleteProvider(id: number): Promise<void>
  syncModels(providerId: number): Promise<ModelSetting[]>
  patchModel(id: number, patch: { enabled?: boolean; display_name?: string }): Promise<ModelSetting>
  listEnabledModels(): Promise<ModelSetting[]>   // GET /settings/models?enabled=true，对话框用
}
```

### 2. `frontend/src/components/SettingsPanel.vue`（新建）

设置页主面板，作为侧边栏或模态框：

**结构：**
```
SettingsPanel
  └── ProviderCard × N
        ├── Provider 名称 / base_url / api_key 输入
        ├── [保存] [同步模型] [删除] 按钮
        └── ModelTable（展开/折叠）
              └── 每行：model_id / display_name / 上下文长度 / [工具] [思考] 标签 / 启用开关
```

**关键交互逻辑：**
- 新增 Provider 表单默认折叠，点"＋ 添加 Provider"展开
- 同步模型后列表展开，已存在的模型保留 enabled 状态
- 每行 enabled 开关变化立即 PATCH（防抖 300ms）

### 3. `frontend/src/components/ModelSelector.vue`（新建）

对话框底部的模型选择器组件：

**Props：**
```typescript
interface Props {
  sessionId: string
  modelId: string | null
  thinkingEnabled: boolean
  thinkingEffort: string
}
emit: ['update:modelId', 'update:thinkingEnabled', 'update:thinkingEffort']
```

**渲染逻辑：**
```
[DeepSeek V4 Flash ▾]  [✦ 思考 ●——○]  [深度: ○低 ●高]
   ↑ 下拉选模型           ↑ 只在 supports_thinking=true 时显示   ↑ 只在 thinking_enabled=true 时显示
```

effort 档位按 `effort_levels` 数组渲染，不硬编码：
- `["low","high"]` → 两档
- `["low","medium","high"]` → 三档
- `[]` → 不显示

选择变化后立即 `PATCH /sessions/{sessionId}` 保存到后端。

### 4. 修改 `frontend/src/components/MessageComposer.vue`

在输入框底部工具栏嵌入 `<ModelSelector>`：

```vue
<!-- 工具栏左侧 -->
<ModelSelector
  :session-id="sessionId"
  v-model:model-id="currentModelId"
  v-model:thinking-enabled="thinkingEnabled"
  v-model:thinking-effort="thinkingEffort"
/>
```

### 5. 修改 `frontend/src/composables/useWorkspace.ts`

session 状态新增字段：
```typescript
interface SessionState {
  // 现有字段...
  model_id: string | null
  thinking_enabled: boolean
  thinking_effort: string
}
```

PATCH session 时把 model 配置一起带上。

### 6. 修改 `frontend/src/App.vue` 或主布局

在顶部导航栏或侧边栏加入设置入口（齿轮图标），点击显示 `SettingsPanel`（侧抽屉或模态）。

---

## 组件职责边界

| 组件 | 负责 | 不负责 |
|------|------|--------|
| `SettingsPanel.vue` | Provider/Model 的增删改同步 | 对话逻辑 |
| `ModelSelector.vue` | 读 enabled 模型、管理 thinking 状态、PATCH session | 调用模型、渲染消息 |
| `MessageComposer.vue` | 嵌入 ModelSelector、传递 sessionId | model 选择逻辑 |
| `useWorkspace.ts` | session 状态（含 model 字段）读写 | UI 渲染 |
| `settings.ts` | 所有 /settings/* API 封装 | 业务状态管理 |

---

## Done Conditions

- [ ] SettingsPanel 可新增 Provider，保存后列表刷新
- [ ] 点"同步模型"后模型列表出现，每行有启用开关
- [ ] ModelSelector 下拉显示 enabled=true 的模型
- [ ] 选择支持 thinking 的模型时，thinking 开关出现
- [ ] 开启 thinking 后，effort 档位按 effort_levels 渲染（不硬编码）
- [ ] 切换模型/thinking 后，PATCH /sessions/{id} 成功，后端 run 时用新配置
- [ ] 切换到不支持 thinking 的模型时，thinking 开关隐藏
