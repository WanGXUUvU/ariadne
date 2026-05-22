<script setup lang="ts">
/**
 * ModelSelector.vue
 * 职责：对话框底部工具栏中的模型选择器 + thinking 开关 + effort 档位
 * 不负责：持久化（由父组件通过 emit 处理）
 *
 * 输入：modelId / thinkingEnabled / thinkingEffort（v-model 双向绑定）
 * 输出：update:modelId / update:thinkingEnabled / update:thinkingEffort
 */
import { ref, computed, onMounted, watch } from 'vue';
import { settingsApi } from '../api/settings';
import type { ModelSetting, Provider } from '../api/settings';

// ── 点击外部关闭下拉的自定义指令 ──
const vClickOutside = {
  mounted(el: HTMLElement, binding: { value: () => void }) {
    (el as any)._clickOutside = (e: MouseEvent) => {
      if (!el.contains(e.target as Node)) binding.value();
    };
    document.addEventListener('click', (el as any)._clickOutside);
  },
  unmounted(el: HTMLElement) {
    document.removeEventListener('click', (el as any)._clickOutside);
  },
};

const props = defineProps<{
  modelId: string | null;
  providerId: number | null;
  thinkingEnabled: boolean;
  thinkingEffort: string;
  /** 父组件正在加载 session 详情时为 true，此时不应触发自动选模型（避免覆盖已保存的模型） */
  sessionLoading?: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:model', payload: { modelId: string | null; providerId: number | null }): void;
  (e: 'update:thinkingEnabled', v: boolean): void;
  (e: 'update:thinkingEffort', v: string): void;
}>();

// ── 数据 ──
const models = ref<ModelSetting[]>([]);
const providers = ref<Provider[]>([]);
const isLoading = ref(true);
const dropdownOpen = ref(false);

// effort 档位中文映射
const effortLabels: Record<string, string> = { low: '低', medium: '中', high: '高' };

// ── 当前选中模型的元信息 ──
const selectedModel = computed(() =>
  models.value.find(m => m.model_id === props.modelId && m.provider_id === props.providerId) ??
  models.value.find(m => m.model_id === props.modelId) ??
  null
);

const displayName = computed(() => {
  if (isLoading.value) return '加载中…';
  if (!selectedModel.value) {
    return models.value.length > 0 ? '选择模型' : '未配置模型';
  }
  return selectedModel.value.display_name || selectedModel.value.model_id;
});

// ── 按 provider 分组的模型列表 ──
const groupedModels = computed(() => {
  return providers.value
    .map(p => ({
      provider: p,
      models: models.value.filter(m => m.provider_id === p.id),
    }))
    .filter(g => g.models.length > 0);
});

// ── 初始化 ──
// 是否已完成过一次自动选模型（防止重复触发）
const autoSelectDone = ref(false);

const fetchModels = async () => {
  try {
    const [fetchedModels, fetchedProviders] = await Promise.all([
      settingsApi.listEnabledModels(),
      settingsApi.listProviders(),
    ]);
    models.value = fetchedModels;
    providers.value = fetchedProviders;
  } catch {
    // 接口失败时静默（可能尚未配置 Provider）
  } finally {
    isLoading.value = false;
  }
};

onMounted(fetchModels);

// 下拉框打开时重新拉取，确保新增 Provider 后立即可见
watch(dropdownOpen, (opened) => {
  if (opened) fetchModels();
});

// 当模型列表加载完 && session 不再加载中 && 没有选中模型时，才自动选第一个
// 这样可以避免在 loadSessionDetail 完成之前提前覆盖已保存的模型
watch(
  [models, () => props.sessionLoading, () => props.modelId],
  ([newModels, loading, modelId]) => {
    if (autoSelectDone.value) return;
    if (newModels.length > 0 && !loading && !modelId) {
      autoSelectDone.value = true;
      const defaultModel = newModels[0];
      emit('update:model', { modelId: defaultModel.model_id, providerId: defaultModel.provider_id });
    }
  }
);

// ── 选择模型 ──
const selectModel = (m: ModelSetting) => {
  emit('update:model', { modelId: m.model_id, providerId: m.provider_id });
  dropdownOpen.value = false;
  // 如果新模型不支持 thinking，自动关闭
  if (!m.supports_thinking && props.thinkingEnabled) {
    emit('update:thinkingEnabled', false);
  }
};

// ── 切换 thinking ──
const toggleThinking = () => {
  emit('update:thinkingEnabled', !props.thinkingEnabled);
};

// ── 切换 effort ──
const selectEffort = (level: string) => {
  emit('update:thinkingEffort', level);
};

// ── 当外部 modelId 变化时，同步检查 thinking 兼容性 ──
watch(() => props.modelId, () => {
  if (selectedModel.value && !selectedModel.value.supports_thinking && props.thinkingEnabled) {
    emit('update:thinkingEnabled', false);
  }
});
</script>

<template>
  <div class="model-selector">
    <!-- 1. 模型下拉选择 -->
    <div class="ms-dropdown-wrap" v-click-outside="() => dropdownOpen = false">
      <button
        class="ms-trigger"
        :class="{ open: dropdownOpen, empty: !selectedModel && !isLoading }"
        @click="dropdownOpen = !dropdownOpen"
        :disabled="isLoading && models.length === 0"
      >
        <span class="ms-trigger-label">{{ displayName }}</span>
        <svg class="ms-chevron" :class="{ open: dropdownOpen }" viewBox="0 0 24 24" width="10" height="10" stroke="currentColor" stroke-width="2.5" fill="none">
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </button>

      <Transition name="ms-drop">
        <div v-if="dropdownOpen && groupedModels.length > 0" class="ms-dropdown">
          <template v-for="group in groupedModels" :key="group.provider.id">
            <div class="ms-group-header">{{ group.provider.name }}</div>
            <button
              v-for="m in group.models"
              :key="m.id"
              class="ms-option"
              :class="{ selected: m.model_id === modelId && m.provider_id === providerId }"
              @click="selectModel(m)"
            >
              <span class="ms-opt-name">{{ m.display_name || m.model_id }}</span>
              <span class="ms-opt-meta">
                <span v-if="m.supports_thinking" class="ms-tag">🧠</span>
                <span v-if="m.supports_tools" class="ms-tag">🔧</span>
                <span v-if="m.context_length" class="ms-ctx">{{ Math.round(m.context_length / 1000) }}K</span>
              </span>
            </button>
          </template>
        </div>
      </Transition>
    </div>

    <!-- 2. Thinking 开关（仅支持 thinking 的模型才显示） -->
    <button
      v-if="selectedModel?.supports_thinking"
      class="ms-thinking-toggle"
      :class="{ on: thinkingEnabled }"
      @click="toggleThinking"
      title="思考模式"
    >
      <span class="ms-thinking-icon">✦</span>
      <span class="ms-thinking-label">思考</span>
      <span class="ms-thinking-dot" :class="{ on: thinkingEnabled }"></span>
    </button>

    <!-- 3. Effort 档位（仅 thinking 开启且有 effort_levels 时显示） -->
    <div
      v-if="thinkingEnabled && selectedModel && selectedModel.effort_levels.length > 0"
      class="ms-effort"
    >
      <span class="ms-effort-label">深度:</span>
      <button
        v-for="level in selectedModel.effort_levels"
        :key="level"
        class="ms-effort-pill"
        :class="{ active: thinkingEffort === level }"
        @click="selectEffort(level)"
      >
        {{ effortLabels[level] || level }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.model-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

/* ── 模型下拉触发器 ── */
.ms-dropdown-wrap {
  position: relative;
}

.ms-trigger {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 4px 8px;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  color: var(--text-secondary, #999);
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
  white-space: nowrap;
  max-width: 180px;
}
.ms-trigger:hover:not(:disabled) {
  color: var(--text-primary, #eee);
  border-color: rgba(255, 255, 255, 0.15);
  background: rgba(255, 255, 255, 0.04);
}
.ms-trigger.open {
  border-color: rgba(255, 255, 255, 0.2);
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-primary, #eee);
}
.ms-trigger.empty {
  color: var(--text-muted, #555);
  font-style: italic;
}
.ms-trigger:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.ms-trigger-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1;
}

.ms-chevron {
  opacity: 0.4;
  transition: transform 0.15s ease;
  flex-shrink: 0;
}
.ms-chevron.open {
  transform: rotate(180deg);
  opacity: 0.7;
}

/* ── 下拉菜单 ── */
.ms-dropdown {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 0;
  min-width: 220px;
  max-height: 240px;
  overflow-y: auto;
  background: rgba(var(--bg-panel-rgb, 10, 10, 10), 0.85) !important;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid var(--border-strong) !important;
  border-radius: 10px;
  padding: 4px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.6), var(--shadow-glow);
  z-index: 100;
}

.ms-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: var(--text-secondary, #999);
  font-size: 11.5px;
  cursor: pointer;
  text-align: left;
  transition: background 0.1s, color 0.1s;
}
.ms-option:hover {
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-primary, #eee);
}
.ms-option.selected {
  color: var(--text-primary, #eee);
  background: rgba(255, 255, 255, 0.05);
}

.ms-opt-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ms-opt-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.ms-tag {
  font-size: 10px;
  line-height: 1;
}

.ms-ctx {
  font-size: 9.5px;
  color: var(--text-muted, #555);
  font-family: var(--font-mono, monospace);
}

/* ── Thinking 开关 ── */
.ms-thinking-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 6px;
  color: var(--text-muted, #666);
  font-size: 11px;
  cursor: pointer;
  transition: color 0.2s, border-color 0.2s, background 0.2s;
  white-space: nowrap;
}
.ms-thinking-toggle:hover {
  color: var(--text-secondary, #999);
  border-color: rgba(255, 255, 255, 0.14);
}
.ms-thinking-toggle.on {
  color: var(--accent);
  border-color: color-mix(in srgb, var(--accent) 30%, transparent);
  background: var(--accent-subtle);
}

.ms-thinking-icon {
  font-size: 10px;
  line-height: 1;
}

.ms-thinking-label {
  line-height: 1;
}

.ms-thinking-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--text-muted, #555);
  transition: background 0.2s, box-shadow 0.2s;
}
.ms-thinking-dot.on {
  background: var(--accent);
  box-shadow: 0 0 6px var(--accent-glow);
}

/* ── Effort 档位选择 ── */
.ms-effort {
  display: flex;
  align-items: center;
  gap: 3px;
}

.ms-effort-label {
  font-size: 10px;
  color: var(--text-muted, #555);
  margin-right: 2px;
  white-space: nowrap;
}

.ms-effort-pill {
  padding: 3px 8px;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 5px;
  color: var(--text-muted, #666);
  font-size: 10.5px;
  cursor: pointer;
  transition: all 0.15s ease;
  line-height: 1;
}
.ms-effort-pill:hover {
  border-color: rgba(255, 255, 255, 0.15);
  color: var(--text-secondary, #999);
}
.ms-effort-pill.active {
  background: var(--accent-subtle);
  border-color: color-mix(in srgb, var(--accent) 35%, transparent);
  color: var(--accent);
  font-weight: 600;
}

/* ── 下拉动画 ── */
.ms-drop-enter-active,
.ms-drop-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.ms-drop-enter-from,
.ms-drop-leave-to {
  opacity: 0;
  transform: translateY(4px) scale(0.97);
}

.ms-group-header {
  padding: 6px 10px 2px;
  font-size: 9.5px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted, #666);
  pointer-events: none;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  margin-bottom: 2px;
}
</style>
