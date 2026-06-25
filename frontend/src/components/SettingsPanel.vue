<script setup lang="ts">
/**
 * SettingsPanel.vue
 * 职责：模型 Provider 管理与模型设置启用面板 (Codex 侧边栏风格升级)
 * 不负责：对话逻辑与会话管理
 */
import { ref, onMounted, watch, computed, nextTick } from 'vue';
import { settingsApi } from '../api/settings';
import type { Provider, ModelSetting } from '../api/settings';
import McpServersSettings from './settings/McpServersSettings.vue';

const props = defineProps<{
  isOpen: boolean;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'skills-changed'): void;
}>();

// ── 导航与标签页管理 ──
const activeTab = ref('general');

const TABS = [
  { id: 'general', name: '常规' },
  { id: 'appearance', name: '外观' },
  { id: 'providers', name: '配置' },
  { id: 'mcp', name: 'MCP 服务器' },
  { id: 'skills', name: '自定义技能' },
] as const;

const currentTabName = computed(() => {
  const t = TABS.find(tab => tab.id === activeTab.value);
  return t ? t.name : '设置';
});

// ── 常规设置状态 (基于 localStorage 实现真实功能) ──
const settingsGeneral = ref({
  autoSave: localStorage.getItem('settings-auto-save') !== 'false',
  sendShortcut: localStorage.getItem('settings-send-shortcut') || 'Enter',
  sidebarFoldersOpen: localStorage.getItem('settings-sidebar-folders') !== 'false',
  streamDelay: parseInt(localStorage.getItem('settings-stream-delay') || '10'),
});

const saveGeneralSettings = () => {
  localStorage.setItem('settings-auto-save', String(settingsGeneral.value.autoSave));
  localStorage.setItem('settings-send-shortcut', settingsGeneral.value.sendShortcut);
  localStorage.setItem('settings-sidebar-folders', String(settingsGeneral.value.sidebarFoldersOpen));
  localStorage.setItem('settings-stream-delay', String(settingsGeneral.value.streamDelay));
};

watch(settingsGeneral, () => {
  saveGeneralSettings();
}, { deep: true });

// ── 状态管理 ──
const providers = ref<Provider[]>([]);
const modelsByProvider = ref<Record<number, ModelSetting[]>>({});
const expandedProviders = ref<Record<number, boolean>>({});
const syncingProviders = ref<Record<number, boolean>>({});
const isLoading = ref(true);
const showAddForm = ref(false);
const errorMsg = ref<string | null>(null);

// 自定义技能状态管理
const skillRoots = ref<{ name: string; path: string }[]>([]);
const showAddSkillRootForm = ref(false);
const newRootName = ref('');
const newRootPath = ref('');

// 编辑 Provider
const editingProviderId = ref<number | null>(null);
const editForm = ref({ name: '', base_url: '', api_key: '' });

// 新增 Provider 表单数据
const newProvider = ref({
  name: '',
  base_url: '',
  api_key: '',
});

// 预设模型提供商定义
interface PresetProvider {
  id: string;
  name: string;
  base_url: string;
  official_url: string;
  description: string;
}

const PRESET_PROVIDERS: PresetProvider[] = [
  {
    id: 'deepseek',
    name: 'DeepSeek',
    base_url: 'https://api.deepseek.com/v1',
    official_url: 'https://platform.deepseek.com/',
    description: '官方 API (V3 / R1)'
  },
  {
    id: 'siliconflow',
    name: 'SiliconFlow',
    base_url: 'https://api.siliconflow.cn/v1',
    official_url: 'https://siliconflow.cn/',
    description: '硅基流动开源模型分发'
  },
  {
    id: 'kimi',
    name: 'Kimi',
    base_url: 'https://api.moonshot.cn/v1',
    official_url: 'https://platform.moonshot.cn/',
    description: '月之暗面 (Moonshot)'
  },
  {
    id: 'zhipu',
    name: 'Zhipu GLM',
    base_url: 'https://open.bigmodel.cn/api/paas/v4',
    official_url: 'https://open.bigmodel.cn/',
    description: '智谱 GLM-4 / GLM-Zero'
  },
  {
    id: 'openrouter',
    name: 'OpenRouter',
    base_url: 'https://openrouter.ai/api/v1',
    official_url: 'https://openrouter.ai/',
    description: '聚合平台 (Claude / GPT)'
  },
  {
    id: 'openai',
    name: 'OpenAI',
    base_url: 'https://api.openai.com/v1',
    official_url: 'https://platform.openai.com/',
    description: '官方 API (GPT-4o / o1 / o3)'
  },
  {
    id: 'minimax',
    name: 'MiniMax',
    base_url: 'https://api.minimax.chat/v1',
    official_url: 'https://platform.minimaxlight.com/',
    description: '官方 API (MiniMax-Text)'
  },
  {
    id: 'qwen',
    name: 'Qwen',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    official_url: 'https://bailian.console.aliyun.com/',
    description: '阿里云百炼兼容接口'
  },
  {
    id: 'ollama',
    name: 'Ollama',
    base_url: 'http://localhost:11434/v1',
    official_url: 'https://ollama.com/',
    description: '本地运行部署 (Local)'
  }
];

const selectedPresetId = ref<string | null>(null);
const apiKeyInputRef = ref<HTMLInputElement | null>(null);

const handleSelectPreset = (preset: PresetProvider) => {
  newProvider.value.name = preset.name;
  newProvider.value.base_url = preset.base_url;
  selectedPresetId.value = preset.id;
  
  nextTick(() => {
    if (apiKeyInputRef.value) {
      apiKeyInputRef.value.focus();
    }
  });
};

// ── 行为方法 ──

const loadSkillRoots = async () => {
  try {
    const settings = await settingsApi.getSettingsFile();
    const roots = settings?.skills?.roots || [];
    skillRoots.value = roots.map((item: any) => ({
      name: item.name || '',
      path: item.path || ''
    }));
  } catch (err: any) {
    errorMsg.value = '获取技能路径失败: ' + err.message;
  }
};

const saveSkillRoots = async (newRoots: { name: string; path: string }[]) => {
  try {
    const settings = await settingsApi.getSettingsFile();
    if (!settings.skills) {
      settings.skills = {};
    }
    settings.skills.roots = newRoots;
    await settingsApi.updateSettingsFile(settings);
    skillRoots.value = newRoots;
    emit('skills-changed');
  } catch (err: any) {
    errorMsg.value = '保存技能路径失败: ' + err.message;
  }
};

const handleAddSkillRoot = async () => {
  if (!newRootName.value.trim() || !newRootPath.value.trim()) {
    errorMsg.value = '请填写路径别名和绝对路径';
    return;
  }
  const updatedRoots = [
    ...skillRoots.value,
    { name: newRootName.value.trim(), path: newRootPath.value.trim() }
  ];
  await saveSkillRoots(updatedRoots);
  newRootName.value = '';
  newRootPath.value = '';
  showAddSkillRootForm.value = false;
};

const handleDeleteSkillRoot = async (index: number) => {
  if (!confirm('确定要删除此技能路径吗？')) return;
  const updatedRoots = skillRoots.value.filter((_, idx) => idx !== index);
  await saveSkillRoots(updatedRoots);
};

// 加载所有 Provider 及其对应的 ModelSettings
const loadAllData = async () => {
  try {
    isLoading.value = true;
    errorMsg.value = null;
    const provs = await settingsApi.listProviders();
    providers.value = provs;
    await loadSkillRoots();
  } catch (err: any) {
    errorMsg.value = '加载设置失败: ' + err.message;
  } finally {
    isLoading.value = false;
  }
};

onMounted(() => {
  if (props.isOpen) {
    loadAllData();
  }
});

// ── 监听 isOpen，开启时自动拉取数据 ──
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
    expandedProviders.value[providerId] = true;
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
    newProvider.value = { name: '', base_url: '', api_key: '' };
    selectedPresetId.value = null;
    showAddForm.value = false;
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
  model.enabled = !model.enabled;
  try {
    await settingsApi.patchModel(model.id, { enabled: model.enabled });
  } catch (err: any) {
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
  document.body.classList.forEach(cls => {
    if (cls.startsWith('theme-')) document.body.classList.remove(cls);
  });
  document.body.classList.add(`theme-${themeId}`);
  localStorage.setItem('agent-build-theme', themeId);
};


</script>

<template>
  <div v-if="isOpen" class="marketplace-modal-overlay" @click.self="$emit('close')">
    <div class="settings-modal">
      
      <!-- 🟢 左侧：顶奢毛玻璃导航侧边栏 -->
      <aside class="settings-sidebar">
        <!-- 返回应用触发器 -->
        <div class="back-to-app-btn" @click="$emit('close')">
          <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2.5" fill="none" class="back-arrow-icon">
            <line x1="19" y1="12" x2="5" y2="12"></line>
            <polyline points="12 19 5 12 12 5"></polyline>
          </svg>
          <span class="back-text">返回应用</span>
        </div>

        <!-- 垂直滚动的设置项列表 -->
        <nav class="sidebar-nav">
          <button 
            v-for="tab in TABS" 
            :key="tab.id"
            class="nav-item"
            :class="{ active: activeTab === tab.id }"
            @click="activeTab = tab.id"
          >
            <span class="active-bar" v-if="activeTab === tab.id"></span>
            <svg class="nav-icon" viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none">
              <template v-if="tab.id === 'general'">
                <circle cx="12" cy="12" r="3"></circle>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
              </template>
              <template v-else-if="tab.id === 'appearance'">
                <circle cx="12" cy="12" r="10"></circle>
                <path d="M12 2v20"></path>
                <path d="M12 6a6 6 0 0 1 6 6 6 6 0 0 1-6 6"></path>
              </template>
              <template v-else-if="tab.id === 'providers'">
                <line x1="4" y1="21" x2="4" y2="14"></line>
                <line x1="4" y1="10" x2="4" y2="3"></line>
                <line x1="12" y1="21" x2="12" y2="12"></line>
                <line x1="12" y1="8" x2="12" y2="3"></line>
                <line x1="20" y1="21" x2="20" y2="16"></line>
                <line x1="20" y1="12" x2="20" y2="3"></line>
                <line x1="1" y1="14" x2="7" y2="14"></line>
                <line x1="9" y1="8" x2="15" y2="8"></line>
                <line x1="17" y1="16" x2="23" y2="16"></line>
              </template>
              <template v-else-if="tab.id === 'mcp'">
                <rect x="3" y="4" width="18" height="6" rx="2"></rect>
                <rect x="3" y="14" width="18" height="6" rx="2"></rect>
                <line x1="7" y1="7" x2="7.01" y2="7"></line>
                <line x1="7" y1="17" x2="7.01" y2="17"></line>
                <line x1="11" y1="7" x2="17" y2="7"></line>
                <line x1="11" y1="17" x2="17" y2="17"></line>
              </template>
              <template v-else-if="tab.id === 'skills'">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"></path>
              </template>
            </svg>
            <span class="nav-label">{{ tab.name }}</span>
          </button>
        </nav>
      </aside>

      <!-- 🔵 右侧：主设置面板内容区 -->
      <main class="settings-content">
        <!-- 头部标题 -->
        <header class="content-header">
          <h2>{{ currentTabName }}</h2>
        </header>

        <!-- 主体区域 -->
        <div class="content-body">
          <!-- 错误提示组件 -->
          <div v-if="errorMsg" class="settings-error">
            <span>{{ errorMsg }}</span>
            <button @click="errorMsg = null">✕</button>
          </div>

          <!-- 1. 常规配置面板 (General Settings) -->
          <div v-if="activeTab === 'general'" class="settings-panel-view">
            <div class="view-description">基础常规设置，直接保存至本地。</div>
            <div class="settings-group">
              <div class="settings-row">
                <div class="row-info">
                  <div class="row-title">自动保存历史记录</div>
                  <div class="row-desc">自动将您的对话会话和历史保存到本地持久化。</div>
                </div>
                <button class="switch-toggle" :class="{ active: settingsGeneral.autoSave }" @click="settingsGeneral.autoSave = !settingsGeneral.autoSave">
                  <span class="switch-dot"></span>
                </button>
              </div>

              <div class="settings-row">
                <div class="row-info">
                  <div class="row-title">发送消息快捷键</div>
                  <div class="row-desc">选择在输入框中提交对话时使用的快捷键组合。</div>
                </div>
                <select v-model="settingsGeneral.sendShortcut" class="premium-select">
                  <option value="Enter">Enter 发送 / Shift+Enter 换行</option>
                  <option value="CmdEnter">Cmd+Enter 发送 / Enter 换行</option>
                </select>
              </div>

              <div class="settings-row">
                <div class="row-info">
                  <div class="row-title">侧边栏文件夹默认展开</div>
                  <div class="row-desc">在加载应用时默认保持工作区组文件夹处于展开状态。</div>
                </div>
                <button class="switch-toggle" :class="{ active: settingsGeneral.sidebarFoldersOpen }" @click="settingsGeneral.sidebarFoldersOpen = !settingsGeneral.sidebarFoldersOpen">
                  <span class="switch-dot"></span>
                </button>
              </div>

              <div class="settings-row">
                <div class="row-info">
                  <div class="row-title">打字机效果延迟 ({{ settingsGeneral.streamDelay }}ms)</div>
                  <div class="row-desc">调整 AI 流式生成文本时的逐字展现延迟。</div>
                </div>
                <input v-model.number="settingsGeneral.streamDelay" type="range" min="0" max="100" step="5" class="premium-slider" />
              </div>

            </div>
          </div>

          <!-- 2. 外观主题配置面板 (Appearance / Theme) -->
          <div v-if="activeTab === 'appearance'" class="settings-panel-view">
            <div class="view-description">界面主题配色方案，即时切换全身变装。</div>
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

          <!-- 3. AI 服务商及模型列表 (Providers & Models Config) -->
          <div v-if="activeTab === 'providers'" class="settings-panel-view">
            <div class="view-description">配置 AI 服务商提供商，并同步及激活其支持的所有模型。</div>
            
            <!-- 加载状态 -->
            <div v-if="isLoading" class="loading-state">
              <span>正在加载服务商列表...</span>
            </div>

            <div v-else class="provider-list">
              <!-- Configuration Header & Add Provider Toggle Card -->
              <div class="provider-card ghost-add-card" :class="{ 'form-open': showAddForm }">
                <div class="ghost-card-trigger" @click="showAddForm = !showAddForm">
                  <span class="ghost-icon">{{ showAddForm ? '✕' : '＋' }}</span>
                  <span class="ghost-text">{{ showAddForm ? '关闭新增表单' : '配置并新增 AI 服务商 (Add Provider)' }}</span>
                </div>

                <!-- Inline Add Form -->
                <Transition name="expand">
                  <div v-if="showAddForm" class="add-provider-inline-form">
                    <!-- Presets Selection Grid -->
                    <div class="preset-section">
                      <div class="preset-title">选择预设快捷配置</div>
                      <div class="preset-grid">
                        <button 
                          v-for="preset in PRESET_PROVIDERS" 
                          :key="preset.id"
                          type="button"
                          class="preset-item"
                          :class="{ active: selectedPresetId === preset.id }"
                          @click="handleSelectPreset(preset)"
                        >
                          <span class="preset-item-name">{{ preset.name }}</span>
                          <span class="preset-item-desc">{{ preset.description }}</span>
                        </button>
                      </div>
                      
                      <!-- Quick Link for API key of the selected preset -->
                      <Transition name="fade">
                        <div v-if="selectedPresetId" class="preset-helper-text">
                          <span class="info-icon">ℹ️</span>
                          已选择 <strong>{{ PRESET_PROVIDERS.find(p => p.id === selectedPresetId)?.name }}</strong>，
                          你可以前往 <a :href="PRESET_PROVIDERS.find(p => p.id === selectedPresetId)?.official_url" target="_blank" class="preset-link">官方控制台</a> 获取 API Key 并填入下方表单。
                        </div>
                      </Transition>
                    </div>

                    <div class="form-grid">
                      <div class="form-group">
                        <label>服务商自定义名称</label>
                        <input v-model="newProvider.name" type="text" placeholder="例如: DeepSeek, OpenAI, Ollama" @input="selectedPresetId = null" />
                      </div>
                      <div class="form-group">
                        <label>API Base URL</label>
                        <input v-model="newProvider.base_url" type="text" placeholder="https://api.deepseek.com/v1" @input="selectedPresetId = null" />
                      </div>
                      <div class="form-group">
                        <label>API Key (密钥)</label>
                        <input ref="apiKeyInputRef" v-model="newProvider.api_key" type="password" placeholder="sk-..." />
                      </div>
                    </div>
                    <div class="form-actions">
                      <button class="save-btn" @click="handleCreateProvider">保存并初始化服务商</button>
                    </div>
                  </div>
                </Transition>
              </div>

              <!-- Real Provider list -->
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

                <!-- Inline Edit Form -->
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

                <!-- Model Settings Table -->
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
                              title="修改以更新显示名称"
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

          <!-- 4. MCP 配置面板 -->
          <div v-if="activeTab === 'mcp'" class="settings-panel-view">
            <McpServersSettings :is-active="activeTab === 'mcp'" />
          </div>

          <!-- 5. 自定义技能配置面板 (Skills Config) -->
          <div v-if="activeTab === 'skills'" class="settings-panel-view">
            <div class="view-description">配置自定义技能 (Skills) 的扫描根目录。系统将扫描该目录下的所有子文件夹，若包含 SKILL.md 则自动加载该技能。</div>
            
            <div class="provider-list">
              <!-- Add Skill Root Toggle Card -->
              <div class="provider-card ghost-add-card" :class="{ 'form-open': showAddSkillRootForm }">
                <div class="ghost-card-trigger" @click="showAddSkillRootForm = !showAddSkillRootForm">
                  <span class="ghost-icon">{{ showAddSkillRootForm ? '✕' : '＋' }}</span>
                  <span class="ghost-text">{{ showAddSkillRootForm ? '关闭新增表单' : '配置并新增技能扫描路径 (Add Skill Root)' }}</span>
                </div>

                <!-- Inline Add Form -->
                <Transition name="expand">
                  <div v-if="showAddSkillRootForm" class="add-provider-inline-form">
                    <div class="form-grid">
                      <div class="form-group">
                        <label>路径别名 (Name)</label>
                        <input v-model="newRootName" type="text" placeholder="例如: my-skills, custom-skills" />
                      </div>
                      <div class="form-group" style="grid-column: span 2;">
                        <label>绝对路径 (Absolute Path)</label>
                        <input v-model="newRootPath" type="text" placeholder="例如: /Users/username/my-skills" />
                      </div>
                    </div>
                    <div class="form-actions">
                      <button class="save-btn" @click="handleAddSkillRoot">保存路径</button>
                    </div>
                  </div>
                </Transition>
              </div>

              <!-- Real Skill Roots list -->
              <div v-if="skillRoots.length === 0" class="models-empty">
                暂未配置任何自定义技能路径。
              </div>
              <div v-else v-for="(root, index) in skillRoots" :key="index" class="provider-card">
                <div class="provider-card-header">
                  <div class="prov-info">
                    <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" style="opacity: 0.7; margin-right: 4px;">
                      <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                    </svg>
                    <span class="prov-name">{{ root.name }}</span>
                    <span class="prov-url mono-text">{{ root.path }}</span>
                  </div>
                  <div class="prov-actions">
                    <button class="delete-icon-btn" @click="handleDeleteSkillRoot(index)" title="删除路径">
                      <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2.5" fill="none">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

        </div>
      </main>

    </div>
  </div>
</template>

<style scoped>
/* ── 最外层遮罩 ── */
.marketplace-modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.75);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

/* ── 顶奢双栏模态大框 ── */
.settings-modal {
  width: 100%;
  max-width: 1080px;
  height: 90vh;
  max-height: 820px;
  background: rgba(var(--bg-panel-rgb, 10, 10, 10), 0.85);
  backdrop-filter: blur(36px);
  -webkit-backdrop-filter: blur(36px);
  border: 1px solid var(--border-strong);
  border-radius: 20px;
  color: var(--text-primary, #eee);
  box-shadow: 0 32px 80px rgba(0, 0, 0, 0.7), 0 0 0 1px rgba(255, 255, 255, 0.03);
  display: flex;
  flex-direction: row;
  overflow: hidden;
  animation: scaleUp 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes scaleUp {
  from { transform: scale(0.96); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}

/* ── 🟢 左侧：顶奢导航栏 ── */
.settings-sidebar {
  width: 240px;
  background: rgba(5, 5, 5, 0.35);
  border-right: 1px solid var(--border-dim);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  padding: 24px 12px;
  overflow-y: auto;
}

/* Mac 点 */
.window-controls {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
  padding-left: 12px;
}

.control-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  cursor: pointer;
  position: relative;
  display: inline-block;
}
.control-dot.close { background: #ef4444; }
.control-dot.minimize { background: #f59e0b; }
.control-dot.maximize { background: #10b981; }

.control-dot:hover::after {
  content: '✕';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: rgba(0,0,0,0.5);
  font-size: 8px;
  font-weight: bold;
}

/* 返回应用按钮 */
.back-to-app-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 8px;
  padding: 10px 16px;
  margin-bottom: 20px;
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
}

.back-to-app-btn:hover {
  background: rgba(var(--accent-rgb, 124, 106, 247), 0.15);
  border-color: var(--accent);
  color: var(--accent);
  box-shadow: 0 0 12px var(--accent-glow);
}

.back-arrow-icon {
  transition: transform 0.2s ease;
}
.back-to-app-btn:hover .back-arrow-icon {
  transform: translateX(-3px);
}

.back-text {
  font-size: 12px;
  font-weight: 600;
}

/* 导航项 */
.sidebar-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}

.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  background: transparent;
  border: none;
  border-radius: 8px;
  color: var(--text-secondary, #999);
  padding: 10px 14px;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s ease;
  user-select: none;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-primary, #eee);
  padding-left: 18px;
}

.nav-item.active {
  background: rgba(var(--accent-rgb, 124, 106, 247), 0.1);
  color: var(--accent);
}

.active-bar {
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 3px;
  background: var(--accent);
  border-radius: 0 3px 3px 0;
}

.nav-icon {
  flex-shrink: 0;
  opacity: 0.7;
}
.nav-item.active .nav-icon {
  opacity: 1;
}

.nav-label {
  font-size: 12px;
  font-weight: 500;
}

/* ── 🔵 右侧：主内容区 ── */
.settings-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: rgba(var(--bg-panel-rgb, 10, 10, 10), 0.25);
}

.content-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 24px 32px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.content-header h2 {
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: var(--text-primary);
}

.close-btn-right {
  background: transparent;
  border: none;
  color: var(--text-muted, #555);
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-btn-right:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.05);
}

.content-body {
  padding: 32px;
  flex: 1;
  overflow-y: auto;
}

/* 通用面板视图 */
.settings-panel-view {
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

.view-description {
  font-size: 12.5px;
  color: var(--text-secondary, #999);
  margin-bottom: 24px;
}

/* ── 错误组件 ── */
.settings-error {
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.15);
  color: #f87171;
  padding: 12px 18px;
  border-radius: 8px;
  font-size: 12px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  font-family: var(--font-mono, monospace);
}
.settings-error button {
  background: transparent;
  border: none;
  color: inherit;
  cursor: pointer;
}

/* ── 1. 常规配置行 ── */
.settings-group {
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-dim);
  border-radius: 12px;
  overflow: hidden;
}

.settings-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid var(--border-dim);
}

.settings-row:last-child {
  border-bottom: none;
}

.row-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 70%;
}

.row-title {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-primary, #ddd);
}

.row-desc {
  font-size: 11.5px;
  color: var(--text-muted, #777);
  line-height: 1.5;
}

/* 常规高端表单元素 */
.premium-select {
  background: var(--bg-panel, #111);
  border: 1px solid var(--border-dim);
  border-radius: 8px;
  color: var(--text-primary);
  font-size: 12px;
  padding: 8px 12px;
  outline: none;
  cursor: pointer;
  transition: all 0.2s ease;
}
.premium-select:focus {
  border-color: var(--accent);
  box-shadow: 0 0 10px var(--accent-glow);
}

.premium-slider {
  -webkit-appearance: none;
  width: 150px;
  height: 4px;
  border-radius: 2px;
  background: rgba(255, 255, 255, 0.1);
  outline: none;
}
.premium-slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--accent);
  cursor: pointer;
  box-shadow: 0 0 8px var(--accent-glow);
  transition: transform 0.1s ease;
}
.premium-slider::-webkit-slider-thumb:hover {
  transform: scale(1.2);
}

/* ── 2. 主题配置格 ── */
.theme-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.theme-card {
  display: flex;
  align-items: center;
  gap: 12px;
  background: rgba(255, 255, 255, 0.02) !important;
  border: 1px solid var(--border-dim) !important;
  border-radius: 10px;
  padding: 12px 18px;
  cursor: pointer;
  color: var(--text-primary);
  text-align: left;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  user-select: none;
}

.theme-card:hover {
  background: rgba(255, 255, 255, 0.04) !important;
  border-color: rgba(255, 255, 255, 0.12) !important;
  transform: translateY(-2px);
}

.theme-card.active {
  border-color: var(--accent) !important;
  background: rgba(var(--accent-rgb, 124, 106, 247), 0.1) !important;
  box-shadow: 0 0 16px var(--accent-glow);
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
  font-size: 12.5px;
  font-weight: 500;
}

/* ── 3. AI 服务商及模型配置 ── */
.provider-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.provider-card {
  background: rgba(255, 255, 255, 0.02) !important;
  border: 1px solid var(--border-dim) !important;
  border-radius: 12px;
  overflow: hidden;
  transition: border-color 0.2s;
}
.provider-card:hover {
  border-color: rgba(255, 255, 255, 0.08);
}

.provider-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 24px;
  cursor: pointer;
  user-select: none;
}

.prov-info {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
  flex: 1;
}

.prov-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #eee);
  flex-shrink: 0;
}

.prov-url {
  font-size: 11.5px;
  color: var(--text-muted, #666);
  font-family: var(--font-mono, monospace);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 320px;
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
  gap: 14px;
}

.sync-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 6px;
  color: var(--text-secondary, #aaa);
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}
.sync-btn:hover:not(:disabled) {
  color: var(--text-primary, #eee);
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.12);
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

.delete-icon-btn, .edit-icon-btn, .star-icon-btn {
  background: transparent;
  border: none;
  color: var(--text-muted, #555);
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  justify-content: center;
}
.delete-icon-btn:hover {
  color: #ef4444;
  background: rgba(239, 68, 68, 0.08);
}
.edit-icon-btn:hover {
  color: var(--accent);
  background: rgba(var(--accent-rgb, 124, 106, 247), 0.08);
}
.star-icon-btn:hover, .star-icon-btn.active {
  color: #ffb800;
  background: rgba(255, 184, 0, 0.08);
}
.star-icon-btn.active .star-icon {
  fill: #ffb800;
}

.expand-chevron {
  color: var(--text-muted, #555);
  transition: transform 0.2s ease;
}
.expand-chevron.open {
  transform: rotate(180deg);
  color: var(--text-secondary);
}

/* 幽灵添加卡 */
.ghost-add-card {
  border: 1px dashed rgba(var(--accent-rgb, 124, 106, 247), 0.3) !important;
  background: rgba(var(--accent-rgb, 124, 106, 247), 0.02) !important;
  transition: all 0.25s ease !important;
}

.ghost-add-card:hover {
  border-color: var(--accent) !important;
  background: rgba(var(--accent-rgb, 124, 106, 247), 0.05) !important;
}

.ghost-card-trigger {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 16px;
  cursor: pointer;
  color: var(--text-secondary);
  font-weight: 500;
  font-size: 12.5px;
}
.ghost-add-card:hover .ghost-card-trigger {
  color: var(--accent);
}

.ghost-icon {
  font-size: 14px;
}

.add-provider-inline-form, .edit-provider-form {
  padding: 20px 24px;
  border-top: 1px solid var(--border-dim);
  background: rgba(0, 0, 0, 0.1);
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
  background: var(--bg-panel, #111) !important;
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
  box-shadow: 0 0 10px var(--accent-glow);
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.save-btn {
  padding: 8px 18px;
  background: var(--accent);
  border: none;
  border-radius: 8px;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s, transform 0.1s;
}
.save-btn:hover {
  opacity: 0.95;
}
.save-btn:active {
  transform: scale(0.97);
}

.cancel-btn {
  background: transparent;
  border: 1px solid var(--border-dim);
  color: var(--text-secondary);
  cursor: pointer;
  padding: 8px 18px;
  border-radius: 8px;
  font-size: 12px;
  transition: all 0.15s;
}
.cancel-btn:hover {
  border-color: var(--text-muted);
  color: var(--text-primary);
}

/* 模型的表格 */
.provider-models-wrapper {
  border-top: 1px solid var(--border-dim) !important;
  background: rgba(0, 0, 0, 0.15) !important;
  padding: 16px 24px;
}

.models-loading, .models-empty {
  font-size: 11.5px;
  color: var(--text-muted, #555);
  padding: 24px 0;
  text-align: center;
}

.models-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  text-align: left;
}

.models-table th {
  padding: 10px;
  color: var(--text-secondary);
  font-weight: 600;
  border-bottom: 1px solid var(--border-dim) !important;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.models-table td {
  padding: 12px 10px;
  border-bottom: 1px solid var(--border-dim) !important;
  color: var(--text-secondary, #bbb);
  vertical-align: middle;
}
.models-table tr.disabled td {
  opacity: 0.45;
}

.td-model-id {
  color: var(--text-primary, #ddd);
}

.model-name-input {
  width: 100%;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 12px;
  color: var(--text-primary, #ddd);
  transition: all 0.15s;
}
.model-name-input:hover {
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(255,255,255,0.06);
}
.model-name-input:focus {
  background: var(--bg-panel, #111) !important;
  border-color: var(--accent);
  outline: none;
}

.td-tags {
  display: flex;
  align-items: center;
  gap: 6px;
}

.cap-tag {
  font-size: 9.5px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 600;
}

.badge-thinking {
  background: rgba(var(--accent-rgb, 124, 106, 247), 0.1);
  color: var(--accent);
  border: 1px solid rgba(var(--accent-rgb, 124, 106, 247), 0.2);
}

.badge-tools {
  background: rgba(52, 211, 153, 0.08);
  color: #34d399;
  border: 1px solid rgba(52, 211, 153, 0.15);
}

/* ── 4. MCP 服务器配置面板 ── */
.mcp-servers-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 24px;
}

.mcp-server-card {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-dim);
  border-radius: 12px;
  padding: 18px 24px;
}

.card-header-main {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.server-meta {
  display: flex;
  align-items: center;
  gap: 10px;
}

.server-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-muted);
}
.server-dot.active {
  background: #10b981;
  box-shadow: 0 0 8px rgba(16, 185, 129, 0.5);
}

.server-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.server-type {
  font-size: 10px;
  background: rgba(255,255,255,0.05);
  color: var(--text-muted);
  padding: 2px 6px;
  border-radius: 4px;
}

.server-status.active {
  font-size: 11px;
  color: #10b981;
  font-weight: 600;
}

.server-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.server-detail-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.detail-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
}

.detail-val {
  font-size: 12px;
  color: var(--text-secondary);
}

.tool-badges {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.tool-badge {
  font-size: 10.5px;
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid var(--border-dim);
  color: var(--text-secondary);
  padding: 3px 8px;
  border-radius: 6px;
  font-family: var(--font-mono, monospace);
}

/* MCP 控制台 */
.mcp-terminal-section {
  border: 1px solid var(--border-dim);
  border-radius: 12px;
  overflow: hidden;
  background: rgba(0, 0, 0, 0.2);
}

.terminal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  cursor: pointer;
  user-select: none;
  background: rgba(255, 255, 255, 0.02);
}

.term-left {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12.5px;
  font-weight: 600;
}

.terminal-icon {
  color: var(--accent);
  font-weight: 800;
}

.chevron {
  font-size: 9px;
  color: var(--text-muted);
  transition: transform 0.2s ease;
}
.chevron.open {
  transform: rotate(180deg);
}

.terminal-body {
  padding: 16px 20px;
  background: rgba(0, 0, 0, 0.4);
  font-size: 11.5px;
  line-height: 1.6;
  max-height: 150px;
  overflow-y: auto;
  border-top: 1px solid var(--border-dim);
}

.log-line {
  color: #a1a1aa;
}
.log-line.success {
  color: #34d399;
}

/* ── 5. 键盘快捷键面板 ── */
.shortcuts-table {
  display: flex;
  flex-direction: column;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-dim);
  border-radius: 12px;
  overflow: hidden;
}

.shortcut-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border-dim);
}
.shortcut-item:last-child {
  border-bottom: none;
}

.shortcut-name {
  font-size: 12.5px;
  color: var(--text-secondary);
}

.shortcut-keys kbd {
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid var(--border-dim);
  border-radius: 4px;
  color: var(--text-primary);
  font-size: 11px;
  padding: 3px 6px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.5);
  font-family: var(--font-mono, monospace);
}

/* ── 6. 使用与计费面板 ── */
.billing-dash {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.billing-card-mini {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-dim);
  border-radius: 12px;
  padding: 18px 24px;
}

.mini-title {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 8px;
}

.mini-value {
  font-size: 20px;
  font-weight: 700;
  margin-bottom: 6px;
}
.mini-value.highlight-cyan {
  color: #22d3ee;
  text-shadow: 0 0 12px rgba(34, 211, 238, 0.3);
}
.mini-value.text-accent {
  color: var(--accent);
  text-shadow: 0 0 12px var(--accent-glow);
}

.mini-subtitle {
  font-size: 10.5px;
  color: var(--text-muted);
}

.progress-section {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-dim);
  border-radius: 12px;
  padding: 20px 24px;
  margin-bottom: 24px;
}

.progress-labels {
  display: flex;
  justify-content: space-between;
  font-size: 12.5px;
  color: var(--text-secondary);
  margin-bottom: 12px;
}

.progress-track {
  height: 6px;
  border-radius: 3px;
  background: rgba(255,255,255,0.06);
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, var(--accent) 0%, #22d3ee 100%);
  box-shadow: 0 0 8px rgba(34, 211, 238, 0.4);
}

.chart-section {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-dim);
  border-radius: 12px;
  padding: 20px 24px;
}

.chart-header {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 20px;
}

.bar-chart-container {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  height: 120px;
  padding: 0 10px;
}

.bar-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  width: 40px;
}

.bar-fill {
  width: 12px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 6px 6px 0 0;
  transition: all 0.3s ease;
  cursor: pointer;
}
.bar-fill:hover {
  background: rgba(255, 255, 255, 0.2);
  transform: scaleY(1.05);
}

.bar-fill.active {
  background: linear-gradient(180deg, var(--accent) 0%, rgba(var(--accent-rgb, 124, 106, 247), 0.3) 100%);
  box-shadow: 0 0 12px var(--accent-glow);
}

.bar-label {
  font-size: 10.5px;
  color: var(--text-muted);
}
.bar-col.active .bar-label {
  color: var(--accent);
  font-weight: 600;
}

/* ── 7. 开发预留 / Draft Mode ── */
.draft-feature-card {
  background: rgba(255, 255, 255, 0.01);
  border: 1px dashed rgba(255, 255, 255, 0.1);
  border-radius: 14px;
  padding: 28px;
  text-align: left;
}

.draft-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}

.draft-badge {
  font-size: 9.5px;
  background: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
  border: 1px solid rgba(245, 158, 11, 0.2);
  padding: 2px 8px;
  border-radius: 4px;
  width: fit-content;
  font-weight: 600;
}

.draft-header h3 {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.draft-desc {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 24px;
}

.mock-fields {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.mock-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-dim);
  border-radius: 8px;
}

.mock-row.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.mock-row span {
  font-size: 12px;
  color: var(--text-secondary);
}

/* ── 开关 (Switch) ── */
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
.switch-toggle:disabled {
  cursor: not-allowed;
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

/* ── 动画过渡 ── */
.expand-enter-active,
.expand-leave-active {
  transition: max-height 0.25s ease-out, opacity 0.2s ease, padding 0.25s ease;
  overflow: hidden;
  max-height: 600px;
}
.expand-enter-from,
.expand-leave-to {
  max-height: 0;
  opacity: 0;
  padding-top: 0 !important;
  padding-bottom: 0 !important;
}

.mono-text {
  font-family: var(--font-mono, monospace);
  font-size: 11px;
}

.preset-section {
  margin-bottom: 20px;
  border-bottom: 1px dashed var(--border-dim);
  padding-bottom: 16px;
}

.preset-title {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted, #666);
  letter-spacing: 0.05em;
  text-transform: uppercase;
  margin-bottom: 10px;
}

.preset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}

.preset-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8px 6px;
  background: rgba(255, 255, 255, 0.01);
  border: 1px solid var(--border-dim);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
  text-align: center;
}

.preset-item:hover {
  border-color: rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.03);
}

.preset-item.active {
  border-color: var(--accent);
  background: rgba(255, 255, 255, 0.04);
  box-shadow: 0 0 8px var(--accent-glow);
}

.preset-item-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary, #eee);
  margin-bottom: 2px;
}

.preset-item-desc {
  font-size: 9px;
  color: var(--text-muted, #666);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.preset-helper-text {
  font-size: 11px;
  color: var(--text-muted, #888);
  background: rgba(255, 255, 255, 0.02);
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid var(--border-dim);
  margin-top: 8px;
  line-height: 1.4;
}

.preset-link {
  color: var(--accent);
  text-decoration: none;
  font-weight: 600;
}

.preset-link:hover {
  text-decoration: underline;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
