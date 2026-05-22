<script setup lang="ts">
/**
 * SettingsPanel.vue
 * 职责：模型 Provider 管理与模型设置启用面板 (模态框样式)
 * 不负责：对话逻辑与会话管理
 */
import { ref, onMounted, watch } from 'vue';
import { settingsApi } from '../api/settings';
import type { Provider, ModelSetting } from '../api/settings';

const props = defineProps<{
  isOpen: boolean;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
}>();

// ── 状态管理 ──
const providers = ref<Provider[]>([]);
const modelsByProvider = ref<Record<number, ModelSetting[]>>({});
const expandedProviders = ref<Record<number, boolean>>({});
const syncingProviders = ref<Record<number, boolean>>({});
const isLoading = ref(true);
const showAddForm = ref(false);
const errorMsg = ref<string | null>(null);

// 编辑 Provider
const editingProviderId = ref<number | null>(null);
const editForm = ref({ name: '', base_url: '', api_key: '' });

// 新增 Provider 表单数据
const newProvider = ref({
  name: '',
  base_url: '',
  api_key: '',
});

// ── 行为方法 ──

// 加载所有 Provider 及其对应的 ModelSettings
const loadAllData = async () => {
  try {
    isLoading.value = true;
    errorMsg.value = null;
    const provs = await settingsApi.listProviders();
    providers.value = provs;

    // 拉取每个 Provider 下的所有模型设置
    // 后端没有直接按 providerId 过滤的接口，但我们可以拉取 enabled + disabled 所有的模型，或者等 sync / 同步模型触发
    // 为了让已有的 model 列表显示，我们可以通过拉取所有模型或前端分类。
    // 实际上后端 settingsApi.listEnabledModels() 只返回已启用的。
    // 为了看到所有已同步的模型，我们需要一个列出全部 model_settings 的后端的接口或者为每个 provider 同步/加载。
    // 等等！TASK-072a 后端实现里：
    // GET /settings/providers/{id}/models 通常用于同步，同时返回同步后的所有 ModelSetting！
    // 我们可以默认调用 syncModels 接口或者后端在 GET /settings/providers 返回时带上 models，或者 listProviders 本身返回 models？
    // 让我们确认一下后端 settingsApi 的 API 结构。在 settings.ts 中我们定义了：
    // syncModels(providerId): GET /settings/providers/{providerId}/models
    // 我们先加载 providers，若展开某个 provider，如果没有加载过其模型，自动调用一次 sync/列表加载。
  } catch (err: any) {
    errorMsg.value = '加载 Provider 列表失败: ' + err.message;
  } finally {
    isLoading.value = false;
  }
};

onMounted(() => {
  if (props.isOpen) {
    loadAllData();
  }
});

// ── 监听 isOpen，开启时自动拉取数据，彻底干掉卡死 Bug ──
watch(() => props.isOpen, (newVal) => {
  if (newVal) {
    loadAllData();
  }
});

// 开始编辑某个 Provider
const startEditProvider = (prov: Provider) => {
  editingProviderId.value = prov.id;
  editForm.value = { name: prov.name, base_url: prov.base_url, api_key: '' };
};

// 取消编辑
const cancelEditProvider = () => {
  editingProviderId.value = null;
};

// 保存编辑
const handleSaveEdit = async (providerId: number) => {
  const patch: { name?: string; base_url?: string; api_key?: string } = {};
  if (editForm.value.name) patch.name = editForm.value.name;
  if (editForm.value.base_url) patch.base_url = editForm.value.base_url;
  if (editForm.value.api_key) patch.api_key = editForm.value.api_key;
  try {
    errorMsg.value = null;
    const updated = await settingsApi.patchProvider(providerId, patch);
    const idx = providers.value.findIndex(p => p.id === providerId);
    if (idx !== -1) providers.value[idx] = updated;
    editingProviderId.value = null;
  } catch (err: any) {
    errorMsg.value = '更新服务商失败: ' + err.message;
  }
};

// 展开/折叠 Provider 卡片，并自动同步/加载模型
const toggleExpandProvider = async (providerId: number) => {
  expandedProviders.value[providerId] = !expandedProviders.value[providerId];
  if (expandedProviders.value[providerId] && !modelsByProvider.value[providerId]) {
    // 第一次展开时，如果还没有模型列表，则自动拉取/同步一次
    await handleSyncModels(providerId);
  }
};

// 同步 Provider 模型列表
const handleSyncModels = async (providerId: number) => {
  try {
    syncingProviders.value[providerId] = true;
    errorMsg.value = null;
    const models = await settingsApi.syncModels(providerId);
    modelsByProvider.value[providerId] = models;
    expandedProviders.value[providerId] = true; // 确保展开
  } catch (err: any) {
    errorMsg.value = `同步模型失败: ${err.message}`;
  } finally {
    syncingProviders.value[providerId] = false;
  }
};

// 创建新 Provider
const handleCreateProvider = async () => {
  if (!newProvider.value.name || !newProvider.value.base_url) {
    errorMsg.value = '请填写 Provider 名称和 API Base URL';
    return;
  }
  try {
    errorMsg.value = null;
    const created = await settingsApi.createProvider({
      name: newProvider.value.name,
      base_url: newProvider.value.base_url,
      api_key: newProvider.value.api_key,
    });
    providers.value.push(created);
    // 重置表单
    newProvider.value = { name: '', base_url: '', api_key: '' };
    showAddForm.value = false;
    // 自动展开并同步新 provider
    await toggleExpandProvider(created.id);
  } catch (err: any) {
    errorMsg.value = '创建 Provider 失败: ' + err.message;
  }
};

// 删除 Provider
const handleDeleteProvider = async (id: number) => {
  if (!confirm('确定要删除此 Provider 吗？这将同时删除该 Provider 下的所有模型设置。')) return;
  try {
    errorMsg.value = null;
    await settingsApi.deleteProvider(id);
    providers.value = providers.value.filter(p => p.id !== id);
    delete modelsByProvider.value[id];
    delete expandedProviders.value[id];
  } catch (err: any) {
    errorMsg.value = '删除 Provider 失败: ' + err.message;
  }
};

// 切换模型启用状态
const toggleModelEnabled = async (model: ModelSetting, providerId: number) => {
  const originalState = model.enabled;
  // 乐观更新 UI
  model.enabled = !model.enabled;
  try {
    await settingsApi.patchModel(model.id, { enabled: model.enabled });
  } catch (err: any) {
    // 失败则回滚状态并报错
    model.enabled = originalState;
    errorMsg.value = `更新模型状态失败: ${err.message}`;
  }
};

// 修改模型显示名称
const updateModelDisplayName = async (model: ModelSetting, newName: string) => {
  const originalName = model.display_name;
  model.display_name = newName;
  try {
    await settingsApi.patchModel(model.id, { display_name: newName });
  } catch (err: any) {
    model.display_name = originalName;
    errorMsg.value = `更新模型显示名称失败: ${err.message}`;
  }
};

// 设为默认服务商
const handleSetDefault = async (providerId: number) => {
  const previousProviders = providers.value.map(p => ({ ...p }));
  providers.value = providers.value.map(p => ({
    ...p,
    is_default: p.id === providerId,
  }));
  try {
    errorMsg.value = null;
    await settingsApi.setDefaultProvider(providerId);
  } catch (err: any) {
    providers.value = previousProviders;
    errorMsg.value = '设置默认服务商失败: ' + err.message;
  }
};

// ── 主题管理 ──
const THEMES = [
  { id: 'default', name: '深空墨黑', colors: ['#000000', '#111111', '#FFFFFF'] },
  { id: 'cyberpunk', name: '赛博魅紫', colors: ['#090514', '#171133', '#A78BFA'] },
  { id: 'emerald', name: '翡翠森林', colors: ['#040D0A', '#112C22', '#10B981'] },
  { id: 'amber', name: '琥珀古金', colors: ['#0D0C0A', '#2E281F', '#F59E0B'] },
  { id: 'light-apple', name: '苹果极简 (雅白)', colors: ['#F5F5F7', '#FFFFFF', '#0071E3'] },
  { id: 'light-openai', name: 'OpenAI (素绿)', colors: ['#F9F9F9', '#FFFFFF', '#10A37F'] },
] as const;

const currentTheme = ref(localStorage.getItem('agent-build-theme') || 'default');

const selectTheme = (themeId: string) => {
  currentTheme.value = themeId;
  document.body.className = `theme-${themeId}`;
  localStorage.setItem('agent-build-theme', themeId);
};
</script>

<template>
  <div v-if="isOpen" class="marketplace-modal-overlay" @click.self="$emit('close')">
    <div class="settings-modal">
      <header class="settings-header">
        <div class="header-left">
          <svg class="settings-title-icon" viewBox="0 0 24 24" width="22" height="22" stroke="var(--accent)" stroke-width="2.2" fill="none">
            <circle cx="12" cy="12" r="3"></circle>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
          </svg>
          <span class="settings-title">模型与服务商设置</span>
        </div>
        <button class="close-btn" @click="$emit('close')">
          <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2.5" fill="none">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </header>

      <div class="settings-body">
        <!-- 错误提示 -->
        <div v-if="errorMsg" class="settings-error">
          <span>{{ errorMsg }}</span>
          <button @click="errorMsg = null">✕</button>
        </div>

        <!-- 💡 界面主题选择区 -->
        <div class="theme-section">
          <h2 class="mono-label section-title">界面主题 (INTERFACE THEME)</h2>
          <div class="theme-grid">
            <button
              v-for="t in THEMES"
              :key="t.id"
              class="theme-card"
              :class="{ active: currentTheme === t.id }"
              @click="selectTheme(t.id)"
            >
              <div class="theme-card-preview">
                <span v-for="c in t.colors" :key="c" class="preview-dot" :style="{ background: c }"></span>
              </div>
              <span class="theme-card-name">{{ t.name }}</span>
            </button>
          </div>
        </div>

        <div class="providers-section-header" style="margin-bottom: 16px;">
          <h2 class="mono-label">AI 服务商 (PROVIDERS)</h2>
        </div>

        <!-- 加载中 -->
        <div v-if="isLoading" class="loading-state">
          <span>正在加载服务商列表...</span>
        </div>

        <!-- Provider 列表 (含首位幽灵新增卡) -->
        <div v-else class="provider-list">
          <!-- 💡 殿堂级创意：列表首项“＋ 新增服务商”幽灵卡片 -->
          <div class="provider-card ghost-add-card" :class="{ 'form-open': showAddForm }">
            <div class="ghost-card-trigger" @click="showAddForm = !showAddForm">
              <span class="ghost-icon">{{ showAddForm ? '✕' : '＋' }}</span>
              <span class="ghost-text">{{ showAddForm ? '关闭新增表单' : '配置并新增 AI 服务商 (Add Provider)' }}</span>
            </div>

            <!-- 内联表单过渡展开 -->
            <Transition name="expand">
              <div v-if="showAddForm" class="add-provider-inline-form">
                <div class="form-grid">
                  <div class="form-group">
                    <label>服务商自定义名称</label>
                    <input v-model="newProvider.name" type="text" placeholder="例如: DeepSeek, OpenAI, Ollama" />
                  </div>
                  <div class="form-group">
                    <label>API Base URL</label>
                    <input v-model="newProvider.base_url" type="text" placeholder="https://api.deepseek.com/v1" />
                  </div>
                  <div class="form-group">
                    <label>API Key (密钥)</label>
                    <input v-model="newProvider.api_key" type="password" placeholder="sk-..." />
                  </div>
                </div>
                <div class="form-actions">
                  <button class="save-btn" @click="handleCreateProvider">保存并初始化服务商</button>
                </div>
              </div>
            </Transition>
          </div>

          <!-- 真实服务商 Bento 卡片列表 -->
          <div v-for="prov in providers" :key="prov.id" class="provider-card">
            <!-- Header -->
            <div class="provider-card-header" @click="toggleExpandProvider(prov.id)">
              <div class="prov-info">
                <span class="prov-name">{{ prov.name }}</span>
                <span class="prov-url">{{ prov.base_url }}</span>
                <span v-if="prov.api_key_hint" class="prov-key-hint">{{ prov.api_key_hint }}</span>
              </div>
              <div class="prov-actions" @click.stop>
                <button
                  class="star-icon-btn"
                  :class="{ active: prov.is_default }"
                  @click="handleSetDefault(prov.id)"
                  :title="prov.is_default ? '默认服务商' : '设为默认服务商'"
                >
                  <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2.5" fill="none" class="star-icon">
                    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                  </svg>
                </button>
                <button
                  class="edit-icon-btn"
                  @click="startEditProvider(prov)"
                  title="编辑服务商信息"
                >
                  <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2.5" fill="none">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                  </svg>
                </button>
                <button
                  class="sync-btn"
                  :disabled="syncingProviders[prov.id]"
                  @click="handleSyncModels(prov.id)"
                  title="拉取并同步服务商的所有模型"
                >
                  <svg class="sync-icon" :class="{ spinning: syncingProviders[prov.id] }" viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2.5" fill="none">
                    <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/>
                  </svg>
                  {{ syncingProviders[prov.id] ? '同步中…' : '同步模型' }}
                </button>
                <button class="delete-icon-btn" @click="handleDeleteProvider(prov.id)" title="删除服务商">
                  <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2.5" fill="none">
                    <polyline points="3 6 5 6 21 6"/>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                  </svg>
                </button>
                <svg class="expand-chevron" :class="{ open: expandedProviders[prov.id] }" viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2.5" fill="none">
                  <polyline points="6 9 12 15 18 9"/>
                </svg>
              </div>
            </div>

            <!-- 内联编辑表单 -->
            <Transition name="expand">
              <div v-if="editingProviderId === prov.id" class="edit-provider-form" @click.stop>
                <div class="form-grid">
                  <div class="form-group">
                    <label>服务商名称</label>
                    <input v-model="editForm.name" type="text" :placeholder="prov.name" />
                  </div>
                  <div class="form-group">
                    <label>API Base URL</label>
                    <input v-model="editForm.base_url" type="text" :placeholder="prov.base_url" />
                  </div>
                  <div class="form-group">
                    <label>API Key（留空保持不变）</label>
                    <input v-model="editForm.api_key" type="password" placeholder="输入新 Key 或留空" />
                  </div>
                </div>
                <div class="form-actions">
                  <button class="save-btn" @click="handleSaveEdit(prov.id)">保存</button>
                  <button class="cancel-btn" @click="cancelEditProvider">取消</button>
                </div>
              </div>
            </Transition>

            <!-- Model Table (展开/折叠) -->
            <Transition name="expand">
              <div v-if="expandedProviders[prov.id]" class="provider-models-wrapper">
                <div v-if="syncingProviders[prov.id] && !modelsByProvider[prov.id]" class="models-loading">
                  正在加载并同步模型中...
                </div>
                <div v-else-if="!modelsByProvider[prov.id] || modelsByProvider[prov.id].length === 0" class="models-empty">
                  暂未同步任何模型，请点击右上方“同步模型”按钮。
                </div>
                <table v-else class="models-table">
                  <thead>
                    <tr>
                      <th>模型 ID</th>
                      <th>显示名称</th>
                      <th>上下文</th>
                      <th>能力标签</th>
                      <th style="text-align: right; width: 80px;">启用</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="model in modelsByProvider[prov.id]" :key="model.id" :class="{ disabled: !model.enabled }">
                      <td class="td-model-id mono-text">{{ model.model_id }}</td>
                      <td class="td-display-name">
                        <input
                          :value="model.display_name || model.model_id"
                          @change="e => updateModelDisplayName(model, (e.target as HTMLInputElement).value)"
                          class="model-name-input"
                          type="text"
                          title="双击或修改以更新显示名称"
                        />
                      </td>
                      <td class="td-ctx mono-text">
                        {{ model.context_length ? `${Math.round(model.context_length / 1024)}K` : '-' }}
                      </td>
                      <td class="td-tags">
                        <span v-if="model.supports_thinking" class="cap-tag badge-thinking" title="支持深度思考">
                          🧠 思考
                        </span>
                        <span v-if="model.supports_tools" class="cap-tag badge-tools" title="支持 Tool Calling">
                          🔧 工具
                        </span>
                      </td>
                      <td style="text-align: right;">
                        <button
                          class="switch-toggle"
                          :class="{ active: model.enabled }"
                          @click="toggleModelEnabled(model, prov.id)"
                        >
                          <span class="switch-dot"></span>
                        </button>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </Transition>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.marketplace-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(8px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.settings-modal {
  width: 100%;
  max-width: 900px;
  height: 100%;
  max-height: 80vh;
  background: rgba(var(--bg-panel-rgb, 10, 10, 10), 0.85);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid var(--border-strong);
  border-radius: 16px;
  overflow-y: auto;
  color: var(--text-primary, #eee);
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255, 255, 255, 0.02);
  display: flex;
  flex-direction: column;
}

.settings-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.settings-title-icon {
  color: var(--accent, #7c6af7);
}

.settings-title {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.close-btn {
  background: transparent;
  border: none;
  color: var(--text-muted, #666);
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
  transition: all 0.15s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}
.close-btn:hover {
  color: var(--text-primary, #eee);
  background: rgba(255, 255, 255, 0.05);
}

.settings-body {
  padding: 24px;
  flex: 1;
  overflow-y: auto;
}

.settings-error {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.2);
  color: #f87171;
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  font-family: var(--font-mono, monospace);
}
.settings-error button {
  background: transparent;
  border: none;
  color: inherit;
  cursor: pointer;
  font-size: 14px;
}

.providers-section-header {
  margin-top: 24px;
}

/* 💡 殿堂级虚线幽灵卡设计 */
.ghost-add-card {
  border: 1px dashed color-mix(in srgb, var(--accent) 35%, var(--border-dim)) !important;
  background: rgba(var(--bg-panel-rgb, 10, 10, 10), 0.15) !important;
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
}

.ghost-add-card:hover {
  border-color: var(--accent) !important;
  background: rgba(var(--bg-panel-rgb, 10, 10, 10), 0.35) !important;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2), 0 0 16px var(--accent-glow) !important;
}

.ghost-card-trigger {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 16px;
  cursor: pointer;
  user-select: none;
  color: var(--text-secondary);
  font-weight: 500;
  font-size: 12.5px;
  transition: color 0.2s;
}

.ghost-add-card:hover .ghost-card-trigger {
  color: var(--accent); /* 悬浮时文字发光 */
}

.ghost-icon {
  font-size: 14px;
  font-weight: bold;
}

/* 内联表单卡片 */
.add-provider-inline-form {
  padding: 0 20px 20px 20px;
  border-top: 1px dashed rgba(255, 255, 255, 0.05);
  margin-top: 4px;
  animation: dropInElastic 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted, #666);
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.form-group input {
  background: var(--bg-panel) !important;
  border: 1px solid var(--border-dim) !important;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 12px;
  color: var(--text-primary, #eee);
  transition: all 0.2s ease;
}
.form-group input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 15%, transparent);
}

.form-actions {
  display: flex;
  justify-content: flex-end;
}

.save-btn {
  padding: 7px 16px;
  background: var(--accent);
  border: none;
  border-radius: 8px;
  color: var(--bg-app, #000);
  font-size: 11.5px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s, transform 0.1s;
}
.save-btn:hover {
  opacity: 0.9;
}
.save-btn:active {
  transform: scale(0.97);
}

/* ---- 状态 ---- */
.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 20px;
  text-align: center;
  color: var(--text-muted, #666);
  font-size: 12px;
}
.empty-icon {
  font-size: 32px;
  margin-bottom: 12px;
}
.empty-text {
  max-width: 320px;
  line-height: 1.6;
}

/* ---- 列表 ---- */
.provider-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.provider-card {
  background: rgba(var(--bg-panel-rgb, 10, 10, 10), 0.3) !important;
  border: 1px solid var(--border-dim) !important;
  border-radius: 12px;
  overflow: hidden;
  transition: border-color 0.2s;
}
.provider-card:hover {
  border-color: rgba(255, 255, 255, 0.1);
}

.provider-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  cursor: pointer;
  user-select: none;
}

.prov-info {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  flex: 1;
}

.prov-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #eee);
  flex-shrink: 0;
}

.prov-url {
  font-size: 11px;
  color: var(--text-muted, #666);
  font-family: var(--font-mono, monospace);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 300px;
}

.prov-key-hint {
  font-size: 10px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-muted, #555);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: var(--font-mono, monospace);
  flex-shrink: 0;
}

.prov-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sync-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  color: var(--text-secondary, #aaa);
  font-size: 10.5px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}
.sync-btn:hover:not(:disabled) {
  color: var(--text-primary, #eee);
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.15);
}
.sync-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.sync-icon {
  flex-shrink: 0;
}
.sync-icon.spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.delete-icon-btn {
  background: transparent;
  border: none;
  color: var(--text-muted, #555);
  cursor: pointer;
  padding: 4px;
  border-radius: 5px;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
}
.delete-icon-btn:hover {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.08);
}

.edit-icon-btn {
  background: transparent;
  border: none;
  color: var(--text-muted, #555);
  cursor: pointer;
  padding: 4px;
  border-radius: 5px;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
}
.edit-icon-btn:hover {
  color: var(--accent, #7c3aed);
  background: rgba(124, 58, 237, 0.08);
}

.star-icon-btn {
  background: transparent;
  border: none;
  color: var(--text-muted, #555);
  cursor: pointer;
  padding: 4px;
  border-radius: 5px;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
}
.star-icon-btn:hover {
  color: #ffb800;
  background: rgba(255, 184, 0, 0.08);
}
.star-icon-btn.active {
  color: #ffb800;
}
.star-icon-btn.active .star-icon {
  fill: #ffb800;
}

.edit-provider-form {
  padding: 14px 16px;
  border-top: 1px solid var(--border-dim);
  background: rgba(0, 0, 0, 0.15);
}

.cancel-btn {
  background: transparent;
  border: 1px solid var(--border-dim);
  color: var(--text-muted, #888);
  cursor: pointer;
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 12px;
  transition: all 0.15s;
}
.cancel-btn:hover {
  color: var(--text-secondary, #bbb);
  border-color: var(--text-muted, #888);
}

.expand-chevron {
  color: var(--text-muted, #555);
  transition: transform 0.2s ease;
}
.expand-chevron.open {
  transform: rotate(180deg);
  color: var(--text-secondary, #999);
}

/* ---- 模型表格 ---- */
.provider-models-wrapper {
  border-top: 1px solid var(--border-dim) !important;
  background: rgba(0, 0, 0, 0.15) !important;
  padding: 12px 20px 20px;
}

.models-loading,
.models-empty {
  font-size: 11px;
  color: var(--text-muted, #555);
  padding: 24px 0;
  text-align: center;
}

.models-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 11.5px;
  text-align: left;
}

.models-table th {
  padding: 8px 10px;
  color: var(--text-secondary);
  font-weight: 600;
  border-bottom: 1px solid var(--border-dim) !important;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.models-table td {
  padding: 10px;
  border-bottom: 1px solid var(--border-dim) !important;
  color: var(--text-secondary, #bbb);
  vertical-align: middle;
}
.models-table tr.disabled td {
  opacity: 0.55;
}

.mono-text {
  font-family: var(--font-mono, monospace);
  font-size: 11px;
}

.td-model-id {
  color: var(--text-primary, #ddd);
}

.td-display-name {
  max-width: 180px;
}

.model-name-input {
  width: 100%;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  padding: 3px 6px;
  font-size: 11.5px;
  color: var(--text-primary, #ddd);
  transition: all 0.15s;
}
.model-name-input:hover {
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(255,255,255,0.06);
}
.model-name-input:focus {
  background: var(--bg-elevated) !important;
  border-color: var(--accent, #7c6af7);
  outline: none;
}

.td-tags {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.cap-tag {
  font-size: 9px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 500;
  white-space: nowrap;
}

.badge-thinking {
  background: color-mix(in srgb, var(--accent) 8%, transparent);
  color: var(--accent);
  border: 1px solid color-mix(in srgb, var(--accent) 15%, transparent);
}

.badge-tools {
  background: rgba(52, 211, 153, 0.08);
  color: #34d399;
  border: 1px solid rgba(52, 211, 153, 0.15);
}

/* ---- 自定义开关 (Switch) ---- */
.switch-toggle {
  width: 32px;
  height: 18px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.08);
  border: none;
  cursor: pointer;
  position: relative;
  transition: background 0.2s;
  display: inline-flex;
  align-items: center;
  padding: 0 2px;
}
.switch-toggle.active {
  background: var(--accent);
}

.switch-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 1px 3px rgba(0,0,0,0.3);
  transition: transform 0.2s cubic-bezier(0.2, 0.9, 0.3, 1);
}
.switch-toggle.active .switch-dot {
  transform: translateX(14px);
}

/* ---- 动画过渡 ---- */
.expand-enter-active,
.expand-leave-active {
  transition: max-height 0.25s ease-out, opacity 0.2s ease, padding 0.25s ease;
  overflow: hidden;
  max-height: 500px;
}
.expand-enter-from,
.expand-leave-to {
  max-height: 0;
  opacity: 0;
  padding-top: 0 !important;
  padding-bottom: 0 !important;
}

/* ---- 💡 主题选择区样式 ---- */
.theme-section {
  margin-bottom: 28px;
  background: rgba(var(--bg-panel-rgb, 10, 10, 10), 0.3) !important;
  border: 1px solid var(--border-dim) !important;
  border-radius: 12px;
  padding: 20px;
}

.section-title {
  margin-bottom: 12px;
  display: block;
}

.theme-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
}

.theme-card {
  display: flex;
  align-items: center;
  gap: 12px;
  background: var(--bg-panel) !important;
  border: 1px solid var(--border-dim) !important;
  border-radius: 8px;
  padding: 10px 16px;
  cursor: pointer;
  color: var(--text-primary);
  text-align: left;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  user-select: none;
}

.theme-card:hover {
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(255, 255, 255, 0.15);
  transform: translateY(-1px);
}

.theme-card.active {
  border-color: var(--accent);
  background: var(--bg-hover);
  box-shadow: 0 0 12px 1px var(--accent-glow);
}

.theme-card-preview {
  display: flex;
  gap: 4px;
  align-items: center;
}

.preview-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.1);
  display: inline-block;
}

.theme-card-name {
  font-size: 12px;
  font-weight: 500;
}
</style>
