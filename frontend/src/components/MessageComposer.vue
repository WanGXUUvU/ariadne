<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue';
import type { SkillMetadata } from '../types';
import ModelSelector from './ModelSelector.vue';

// 点击组件外部时关闭菜单的自定义指令
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

const props = withDefaults(defineProps<{
  disabled: boolean;
  messageCount?: number;
  isStreaming?: boolean;
  permissionProfile?: string;
  sessionId: string | null;
  modelId: string | null;
  providerId: number | null;
  thinkingEnabled: boolean;
  thinkingEffort: string;
  contextTokens?: number;
  contextLength?: number;
  isCompacting?: boolean;
  /** 当前 session 详情正在加载中，张 ModelSelector 自动选模型 */
  sessionLoading?: boolean;
  /** 可用的 skill 列表，用于斜杠命令菜单 */
  skills?: SkillMetadata[];
}>(), {
  contextTokens: 0,
  contextLength: 128000,
  isCompacting: false,
  skills: () => [] as SkillMetadata[],
});

const emit = defineEmits<{
  (e: 'send', text: string, skillName?: string | null): void;
  (e: 'stop'): void;
  (e: 'update:permissionProfile', profile: string): void;
  (e: 'update:model', val: { modelId: string | null; providerId: number | null }): void;
  (e: 'update:thinkingEnabled', val: boolean): void;
  (e: 'update:thinkingEffort', val: string): void;
  (e: 'compact'): void;
}>();

const PROFILES = [
  {
    id: 'conservative',
    label: '监督模式',
    subtitle: 'MANUAL',
    description: '每步操作需你点头，完全掌控执行过程',
    color: '#FF4B4B',
    colorDim: 'rgba(255, 75, 75, 0.1)',
  },
  {
    id: 'standard',
    label: '均衡模式',
    subtitle: 'INTERACTIVE',
    description: '常规操作自动完成，敏感操作再来问你',
    color: '#FFAA00',
    colorDim: 'rgba(255, 170, 0, 0.1)',
  },
  {
    id: 'full-auto',
    label: '自主模式',
    subtitle: 'AUTONOMOUS',
    description: '放开双手，让 Agent 全权处理',
    color: '#0FB97F',
    colorDim: 'rgba(15, 185, 127, 0.1)',
  },
] as const;

const text = ref('');
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const isFocused = ref(false);
const showProfileMenu = ref(false);
const showComposerCtx = ref(false);

// ── 发送快捷键配置监听 ──
const sendShortcut = ref(localStorage.getItem('settings-send-shortcut') || 'Enter');

watch(isFocused, (newVal) => {
  if (newVal) {
    sendShortcut.value = localStorage.getItem('settings-send-shortcut') || 'Enter';
  }
});

const sendShortcutHint = computed(() => {
  if (sendShortcut.value === 'CmdEnter') {
    return '<kbd>⌘↩</kbd> send &nbsp;<kbd>↩</kbd> newline';
  }
  return '<kbd>↩</kbd> send &nbsp;<kbd>⇧↩</kbd> newline';
});

// ── 斜杠命令菜单 ──
const showSlashMenu = ref(false);
const slashQuery = ref('');
const selectedSkillName = ref<string | null>(null);
const slashMenuIndex = ref(0);

// 固定命令列表
const FIXED_COMMANDS = [
  { id: 'compact', label: 'compact', description: '压缩当前对话上下文', icon: '⚡️' },
  { id: 'fork', label: 'fork', description: '从当前会话克隆派生出一个新的分支会话', icon: '⌥' },
];

// 合并固定命令 + skill 列表的过滤结果
const slashMenuItems = computed(() => {
  const q = slashQuery.value.toLowerCase();
  const fixed = FIXED_COMMANDS
    .filter(c => c.label.includes(q))
    .map(c => ({ type: 'command' as const, id: c.id, label: c.label, description: c.description, icon: c.icon }));
  const skills = (props.skills ?? [])
    .filter(s => s.enabled && s.name.toLowerCase().includes(q))
    .map(s => ({ type: 'skill' as const, id: s.name, label: s.name, description: s.description ?? '', icon: '📚' }));
  return [...fixed, ...skills];
});

const currentProfile = () =>
  PROFILES.find(p => p.id === (props.permissionProfile ?? 'conservative')) ?? PROFILES[0];

const selectProfile = (id: string) => {
  emit('update:permissionProfile', id);
  showProfileMenu.value = false;
};

const adjustHeight = () => {
  if (!textareaRef.value) return;
  textareaRef.value.style.height = 'auto';
  textareaRef.value.style.height = `${Math.min(textareaRef.value.scrollHeight, 160)}px`;
};

watch(text, (val) => {
  nextTick(adjustHeight);
  // 检测是否输入 / 开头的命令
  if (val.startsWith('/')) {
    slashQuery.value = val.slice(1).toLowerCase();
    showSlashMenu.value = true;
    slashMenuIndex.value = 0;
  } else {
    showSlashMenu.value = false;
    slashQuery.value = '';
  }
});

const selectSlashItem = (item: typeof slashMenuItems.value[number]) => {
  if (item.type === 'command' && item.id === 'compact') {
    text.value = '';
    showSlashMenu.value = false;
    emit('compact');
    return;
  }
  if (item.type === 'command' && item.id === 'fork') {
    text.value = '/fork ';
    showSlashMenu.value = false;
    nextTick(() => {
      if (textareaRef.value) {
        textareaRef.value.focus();
        textareaRef.value.selectionStart = textareaRef.value.selectionEnd = text.value.length;
      }
    });
    return;
  }
  if (item.type === 'skill') {
    selectedSkillName.value = item.id;
    text.value = '';
    showSlashMenu.value = false;
    nextTick(() => textareaRef.value?.focus());
  }
};

const clearSelectedSkill = () => {
  selectedSkillName.value = null;
};

const handleSend = () => {
  if (!text.value.trim() || (props.disabled && !props.isStreaming)) return;
  emit('send', text.value.trim(), selectedSkillName.value);
  text.value = '';
  selectedSkillName.value = null;
  nextTick(adjustHeight);
};

const handleKeyDown = (e: KeyboardEvent) => {
  // 菜单开着时用方向键和 Enter 导航
  if (showSlashMenu.value && slashMenuItems.value.length > 0) {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      slashMenuIndex.value = (slashMenuIndex.value + 1) % slashMenuItems.value.length;
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      slashMenuIndex.value = (slashMenuIndex.value - 1 + slashMenuItems.value.length) % slashMenuItems.value.length;
      return;
    }
    if (e.key === 'Enter') {
      if (e.isComposing || e.keyCode === 229) return;
      e.preventDefault();
      selectSlashItem(slashMenuItems.value[slashMenuIndex.value]);
      return;
    }
    if (e.key === 'Escape') {
      showSlashMenu.value = false;
      return;
    }
  }
  
  if (e.key === 'Enter') {
    if (e.isComposing || e.keyCode === 229) return;
    
    // 如果配置为 Cmd+Enter 发送
    if (sendShortcut.value === 'CmdEnter') {
      if (e.metaKey || e.ctrlKey) {
        e.preventDefault();
        handleSend();
      }
      // Enter 单独按默认换行
    } else {
      // Enter 直接发送，Shift+Enter 换行
      if (!e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    }
  }
  // Backspace 清除已选 skill
  if (e.key === 'Backspace' && selectedSkillName.value && !text.value) {
    selectedSkillName.value = null;
  }
};

// ── 环状用量计算 ──
const usedPct = computed(() => {
  if (!props.contextLength) return 0;
  return Math.min(100, (props.contextTokens / props.contextLength) * 100);
});

const strokeCircumference = 62.8318; // 2 * pi * 10
const strokeDashoffset = computed(() => {
  return strokeCircumference * (1 - usedPct.value / 100);
});

const usedColor = computed(() => {
  if (usedPct.value > 80) return '#ff453a';
  if (usedPct.value > 60) return '#f59e0b';
  return 'var(--accent)';
});

function fmtTokens(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}

const handleCompact = () => {
  emit('compact');
  showComposerCtx.value = false;
};

defineExpose({
  setText(val: string) {
    text.value = val;
    nextTick(adjustHeight);
  }
});
</script>

<template>
  <div class="composer-container">
    <!-- 斜杠命令菜单 -->
    <Transition name="slash-menu">
      <div v-if="showSlashMenu && slashMenuItems.length > 0" class="slash-menu">
        <div class="slash-menu-header">命令 &amp; 技能</div>
        <div
          v-for="(item, idx) in slashMenuItems"
          :key="item.id"
          class="slash-item"
          :class="{ active: idx === slashMenuIndex, 'is-skill': item.type === 'skill' }"
          @mousedown.prevent="selectSlashItem(item)"
          @mouseover="slashMenuIndex = idx"
        >
          <div class="slash-item-main">
            <span class="slash-item-label"><span class="slash-prefix">/</span>{{ item.label }}</span>
            <span v-if="item.type === 'skill'" class="slash-item-tag">skill</span>
          </div>
          <span class="slash-item-desc">{{ item.description }}</span>
        </div>
      </div>
    </Transition>

    <div class="composer-header mono-label">
      <span class="composer-hint">Ask anything</span>
      <div style="display: flex; gap: 16px; align-items: center;">
        <span v-if="messageCount !== undefined && messageCount > 0" class="turn-counter" :class="{ 'turn-warn': messageCount >= 10 }">
          {{ messageCount }} msg
        </span>
        <span class="key-hint" v-html="sendShortcutHint"></span>
      </div>
    </div>

    <!-- 权限与模型配置工具栏 -->
    <div class="composer-toolbar">
      <div class="profile-selector">
        <div class="profile-dropdown-wrap" v-click-outside="() => showProfileMenu = false">
          <button
            class="profile-trigger"
            :style="{ '--profile-color': currentProfile().color, '--profile-color-dim': currentProfile().colorDim }"
            @click="showProfileMenu = !showProfileMenu"
            :disabled="disabled && !isStreaming"
          >
            <span class="profile-dot-ring" :style="{ '--active-color': currentProfile().color }">
              <span class="profile-dot-inner"></span>
            </span>
            <span class="profile-trigger-label">{{ currentProfile().label }}</span>
            <svg class="profile-chevron" :class="{ open: showProfileMenu }" viewBox="0 0 24 24" width="10" height="10" stroke="currentColor" stroke-width="2.5" fill="none">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </button>

          <div v-if="showProfileMenu" class="profile-menu">
            <button
              v-for="p in PROFILES"
              :key="p.id"
              class="profile-menu-item"
              :class="{ active: (permissionProfile ?? 'conservative') === p.id }"
              :style="{ '--item-color': p.color }"
              @click="selectProfile(p.id)"
            >
              <span class="profile-dot-ring" :style="{ '--active-color': p.color }">
                <span class="profile-dot-inner"></span>
              </span>
              <div class="item-body">
                <div class="item-label-row">
                  <span class="item-label">{{ p.label }}</span>
                  <span class="item-sub-tag" :style="{ color: p.color, background: p.colorDim }">{{ p.subtitle }}</span>
                </div>
                <span class="item-desc">{{ p.description }}</span>
              </div>
              <svg v-if="(permissionProfile ?? 'conservative') === p.id" class="item-check" viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2.5" fill="none">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
            </button>
          </div>
        </div>
      </div>

      <ModelSelector
        v-if="sessionId"
        :model-id="modelId"
        :provider-id="providerId"
        :thinking-enabled="thinkingEnabled"
        :thinking-effort="thinkingEffort"
        :session-loading="sessionLoading"
        @update:model="val => emit('update:model', val)"
        @update:thinking-enabled="val => emit('update:thinkingEnabled', val)"
        @update:thinking-effort="val => emit('update:thinkingEffort', val)"
      />
    </div>

    <div class="composer-wrapper" :class="{ 'is-disabled': disabled && !isStreaming, 'is-focused': isFocused, 'is-streaming': isStreaming }">
      <span v-if="selectedSkillName" class="inline-skill-chip">
        /{{ selectedSkillName }}<button class="inline-skill-clear" @click="clearSelectedSkill" tabindex="-1">×</button>
      </span>
      <textarea 
        ref="textareaRef"
        class="composer-input"
        v-model="text"
        @input="adjustHeight"
        @keydown="handleKeyDown"
        @focus="isFocused = true"
        @blur="isFocused = false"
        :placeholder="selectedSkillName ? '' : 'Ask anything or request a tool...'"
        :disabled="disabled && !isStreaming"
        rows="1"
      ></textarea>

      <!-- 💡 环形上下文窗口用量展示 (置于输入框右侧) -->
      <div v-if="sessionId" class="composer-ctx-ring-wrap" v-click-outside="() => showComposerCtx = false">
        <button
          class="composer-ctx-btn"
          :class="{ warning: usedPct >= 60 && usedPct < 80, danger: usedPct >= 80 }"
          @click="showComposerCtx = !showComposerCtx"
          title="Context Window Usage"
        >
          <svg class="ctx-ring-svg" width="26" height="26">
            <circle cx="13" cy="13" r="10" class="ring-bg" />
            <circle
              cx="13"
              cy="13"
              r="10"
              class="ring-progress"
              :stroke-dasharray="strokeCircumference"
              :stroke-dashoffset="strokeDashoffset"
            />
          </svg>
          <span class="ctx-pct-text">{{ Math.round(usedPct) }}%</span>
        </button>

        <!-- 💡 玻璃拟态上下文卡片弹窗 -->
        <Transition name="composer-ctx-pop">
          <div v-if="showComposerCtx" class="composer-ctx-popover">
            <div class="composer-ctx-header">
              <span class="ctx-header-title">上下文令牌窗口</span>
              <span class="ctx-header-desc">{{ fmtTokens(contextTokens ?? 0) }} / {{ fmtTokens(contextLength ?? 128000) }}</span>
            </div>
            
            <div class="composer-ctx-bar-track">
              <div class="composer-ctx-bar-used" :style="{ width: `${usedPct}%`, background: usedColor }" />
            </div>

            <div class="composer-ctx-meta-row">
              <span>已使用比例</span>
              <span class="meta-val">{{ usedPct.toFixed(1) }}%</span>
            </div>

            <button
              class="composer-ctx-compact-btn"
              :disabled="isCompacting || disabled"
              @click="handleCompact"
            >
              <svg v-if="isCompacting" class="spin-icon" viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none">
                <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
              </svg>
              <span>{{ isCompacting ? '正在压缩对话...' : '压缩当前对话' }}</span>
            </button>
          </div>
        </Transition>
      </div>

      <button 
        class="send-btn"
        :class="{ 'is-stop': isStreaming && !text.trim() }"
        @click="(isStreaming && !text.trim()) ? emit('stop') : handleSend()"
        :disabled="!isStreaming && (disabled || !text.trim())"
        :title="(isStreaming && !text.trim()) ? 'Stop generation' : 'Send'"
      >
        <!-- Stop 正方形图标 -->
        <svg v-if="isStreaming && !text.trim()" viewBox="0 0 24 24" width="12" height="12" fill="currentColor">
          <rect x="4" y="4" width="16" height="16" rx="3"/>
        </svg>
        <!-- 发送箭头图标 -->
        <svg v-else viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
          <line x1="12" y1="19" x2="12" y2="5"></line>
          <polyline points="5 12 12 5 19 12"></polyline>
        </svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
/* ── 斜杠命令菜单 ── */
.slash-menu {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 0;
  right: 0;
  background: var(--bg-elevated, #111111);
  border: 1px solid var(--border-strong);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.25), 0 1px 0 var(--border-dim) inset;
  z-index: 100;
  max-height: 260px;
  overflow-y: auto;
}

.slash-menu-header {
  padding: 8px 14px 6px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border-dim);
}

.slash-item {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding: 8px 14px;
  cursor: pointer;
  transition: background 0.1s;
  border-left: 2px solid transparent;
}

.slash-item.active,
.slash-item:hover {
  background: var(--bg-hover);
  border-left-color: var(--accent);
}

.slash-item-main {
  display: flex;
  align-items: center;
  gap: 8px;
}

.slash-item-label {
  font-family: var(--font-mono, monospace);
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.slash-prefix {
  color: var(--text-secondary);
  font-weight: 400;
}

.slash-item-tag {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  background: var(--accent-subtle);
  color: var(--accent);
  border-radius: 4px;
  padding: 1px 5px;
}

.slash-item-desc {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  padding-left: 10px;
}

/* ── 对话框内行内 skill 标签 ── */
.inline-skill-chip {
  display: inline-flex;
  align-items: center;
  align-self: center;
  flex-shrink: 0;
  background: var(--accent-subtle);
  color: var(--accent);
  border-radius: 6px;
  padding: 2px 4px 2px 8px;
  margin-right: 6px;
  font-family: var(--font-mono, monospace);
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
  animation: chipIn 0.15s cubic-bezier(0.34, 1.56, 0.64, 1);
}

@keyframes chipIn {
  from { opacity: 0; transform: scale(0.9); }
  to   { opacity: 1; transform: scale(1); }
}

.inline-skill-clear {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 0 4px;
  font-size: 14px;
  line-height: 1;
  transition: color 0.1s;
}

.inline-skill-clear:hover {
  color: var(--danger, #ff453a);
}

/* ── 菜单进出动画 ── */
.slash-menu-enter-active,
.slash-menu-leave-active {
  transition: opacity 0.12s, transform 0.12s;
}
.slash-menu-enter-from,
.slash-menu-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

.composer-container {
  padding: 20px 32px 32px;
  background: linear-gradient(to top, var(--bg-app) 75%, transparent);
  position: relative;
  z-index: 10;
}

.composer-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  color: var(--text-muted);
  font-size: 10px;
}

.composer-wrapper {
  display: flex;
  align-items: flex-end;
  /* 💡 玻璃拟态设计：基于当前主题底色 + 强毛玻璃磨砂 */
  background: rgba(var(--bg-panel-rgb, 10, 10, 10), 0.6) !important;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  /* 💡 极细的透亮边框 */
  border: 1px solid var(--border-dim);
  border-radius: 20px;
  padding: 10px 14px;
  /* 💡 平滑弹性过渡 */
  transition: border-color 0.25s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.25s cubic-bezier(0.4, 0, 0.2, 1), transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 8px 32px -8px rgba(0, 0, 0, 0.35), 0 0 0 1px rgba(255, 255, 255, 0.01);
  position: relative;
}

/* 氛围光旋转层（在输入框背后转圈） */
@property --ambient-angle {
  syntax: '<angle>';
  inherits: false;
  initial-value: 0deg;
}

@keyframes ambient-rotate {
  to { --ambient-angle: 360deg; }
}

.composer-wrapper::before {
  content: '';
  position: absolute;
  /* 💡 贴合边框外沿：向外延伸 1px */
  inset: -1px;
  /* 💡 圆角微调以契合输入框的 20px 圆角外轮廓 */
  border-radius: 21px;
  /* 💡 增加内边距作为边框的可见宽度 (1px 极细光轨) */
  padding: 1px;
  /* 💡 渐变带适配当前激活的主题色变量 */
  background: conic-gradient(
    from var(--ambient-angle),
    transparent 50%,
    var(--accent) 80%,
    var(--accent-glow) 95%,
    var(--accent) 100%
  );
  /* 💡 双层线性渐变遮罩合成：扣除内侧内容区，只保留 padding 区域的 1px 光轨 */
  -webkit-mask: 
    linear-gradient(#fff 0 0) content-box, 
    linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  pointer-events: none;
  /* 💡 置于 z-index 2 层，从而精准盖在原本的边框之上 */
  z-index: 2;
  opacity: 0;
  transition: opacity 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

/* 聚焦或流式生成时激活旋转发光细带 */
.composer-wrapper.is-focused::before {
  opacity: 1;
  animation: ambient-rotate 4.5s linear infinite;
}

.composer-wrapper.is-streaming::before {
  opacity: 1;
  animation: ambient-rotate 2s linear infinite;
}

.composer-wrapper.is-focused {
  border-color: transparent;
  /* 💡 聚焦时，极具克制的高阶阴影，无大范围发光扩散 */
  box-shadow: 0 12px 40px -8px rgba(0, 0, 0, 0.6), 
              0 0 0 1px rgba(255, 255, 255, 0.02);
  transform: translateY(-1.5px);
}

.composer-hint {
  color: var(--text-muted);
  font-size: 10px;
  letter-spacing: 0.05em;
}
.turn-counter {
  color: var(--text-muted);
  font-size: 10px;
  font-family: var(--font-mono, monospace);
}
.turn-warn {
  color: var(--accent);
}
.key-hint {
  font-size: 10px;
  color: var(--text-muted);
  opacity: 0.7;
}
.key-hint kbd {
  font-family: var(--font-mono, monospace);
  background: var(--bg-hover);
  border: 1px solid var(--border-dim);
  border-radius: 3px;
  padding: 1px 4px;
  font-size: 9px;
}

/* 权限与模型配置工具栏 */
.composer-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  flex-wrap: wrap;
  gap: 8px;
}

/* 权限模式选择器 */
.profile-selector {
  position: relative;
}

.profile-dropdown-wrap {
  position: relative;
  display: inline-block;
}

/* 触发按钮 */
.profile-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border: 1px solid var(--border-dim);
  border-radius: 6px;
  background: var(--bg-hover);
  cursor: pointer;
  color: var(--text-secondary, #aaa);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.02em;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
  white-space: nowrap;
}
.profile-trigger:hover:not(:disabled) {
  color: var(--text-primary, #eee);
  border-color: var(--border-strong);
  background: var(--bg-active);
}

/* 呼吸质感环形灯 */
.profile-dot-ring {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 1.5px solid var(--active-color);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  position: relative;
  transition: all 0.25s ease;
  flex-shrink: 0;
}

.profile-dot-inner {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: var(--active-color);
  box-shadow: 0 0 6px var(--active-color);
  transition: all 0.25s ease;
}

.profile-trigger:hover .profile-dot-inner {
  transform: scale(1.25);
  box-shadow: 0 0 8px var(--active-color);
}

.profile-trigger-label {
  line-height: 1;
}

.profile-chevron {
  opacity: 0.4;
  transition: transform 0.15s ease;
  flex-shrink: 0;
}
.profile-chevron.open {
  transform: rotate(180deg);
  opacity: 0.7;
}

/* 下拉菜单 */
.profile-menu {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  width: 280px;
  background: rgba(var(--bg-panel-rgb, 10, 10, 10), 0.85) !important;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--border-strong) !important;
  border-radius: 12px;
  padding: 6px;
  box-shadow: 0 16px 48px rgba(0,0,0,0.6), var(--shadow-glow);
  z-index: 100;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.profile-menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  text-align: left;
  width: 100%;
  transition: background 0.12s, border-color 0.12s;
  position: relative;
  overflow: hidden;
}
.profile-menu-item:hover {
  background: var(--bg-hover);
}
.profile-menu-item.active {
  background: var(--bg-active);
  border-color: var(--border-dim);
}
/* 激活项左侧彩色竖条 */
.profile-menu-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 25%;
  bottom: 25%;
  width: 2px;
  border-radius: 2px;
  background: var(--item-color, #fff);
}

.item-body {
  display: flex;
  flex-direction: column;
  gap: 3px;
  flex: 1;
  min-width: 0;
}

.item-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.item-label {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.01em;
}

.item-sub-tag {
  font-family: var(--font-mono, monospace);
  font-size: 8.5px;
  font-weight: 600;
  padding: 1px 4px;
  border-radius: 4px;
  letter-spacing: 0.05em;
}

.item-desc {
  font-size: 10.5px;
  color: var(--text-secondary);
  line-height: 1.4;
}

.item-check {
  color: var(--accent);
  flex-shrink: 0;
  opacity: 0.8;
}

.composer-input {
  flex: 1;
  background: transparent;
  border: none;
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.5;
  padding: 4px 0;
  resize: none;
  min-height: 24px;
  max-height: 200px;
  margin-right: 8px;
}

.composer-input:focus {
  outline: none;
}

.composer-input::placeholder {
  color: var(--text-muted);
}

/* ── Sleek Context Ring Indicator ── */
.composer-ctx-ring-wrap {
  position: relative;
  margin-right: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.composer-ctx-btn {
  background: transparent;
  border: none;
  width: 32px;
  height: 32px;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  cursor: pointer;
  border-radius: 50%;
  transition: background-color 0.2s, transform 0.2s;
}

.composer-ctx-btn:hover {
  background: var(--bg-hover);
  transform: scale(1.05);
}

.composer-ctx-btn:active {
  transform: scale(0.95);
}

.ctx-ring-svg {
  transform: rotate(-90deg);
  transform-origin: center;
  display: block;
}

.ring-bg {
  stroke: var(--border-dim);
  stroke-width: 2.2;
  fill: none;
}

.ring-progress {
  stroke: var(--accent);
  stroke-width: 2.2;
  stroke-linecap: round;
  fill: none;
  transition: stroke-dashoffset 0.35s ease, stroke 0.35s ease;
}

.composer-ctx-btn.warning .ring-progress {
  stroke: #f59e0b;
}

.composer-ctx-btn.danger .ring-progress {
  stroke: #ff453a;
  filter: drop-shadow(0 0 2px rgba(255, 69, 58, 0.6));
}

.ctx-pct-text {
  position: absolute;
  font-family: var(--font-mono, monospace);
  font-size: 8px;
  font-weight: 600;
  color: var(--text-muted);
  transition: color 0.2s;
}

.composer-ctx-btn:hover .ctx-pct-text {
  color: var(--text-primary);
}

.composer-ctx-btn.warning .ctx-pct-text {
  color: #f59e0b;
}

.composer-ctx-btn.danger .ctx-pct-text {
  color: #ff453a;
}

/* ── Context Details Glass Popover ── */
.composer-ctx-popover {
  position: absolute;
  bottom: calc(100% + 12px);
  right: 0;
  width: 220px;
  background: rgba(var(--bg-panel-rgb, 10, 10, 10), 0.85) !important;
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--border-strong) !important;
  border-radius: 12px;
  padding: 12px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.6), var(--shadow-glow);
  z-index: 100;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.composer-ctx-header {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ctx-header-title {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-primary);
}

.ctx-header-desc {
  font-family: var(--font-mono, monospace);
  font-size: 10px;
  color: var(--text-muted);
}

.composer-ctx-bar-track {
  height: 4px;
  background: var(--border-dim);
  border-radius: 2px;
  overflow: hidden;
}

.composer-ctx-bar-used {
  height: 100%;
  border-radius: 2px;
  transition: width 0.35s ease, background 0.35s ease;
}

.composer-ctx-meta-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 10.5px;
  color: var(--text-secondary);
}

.meta-val {
  font-family: var(--font-mono, monospace);
  font-weight: 500;
  color: var(--text-primary);
}

.composer-ctx-compact-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  padding: 6px 0;
  background: var(--bg-hover);
  border: 1px solid var(--border-dim);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}

.composer-ctx-compact-btn:hover:not(:disabled) {
  background: var(--bg-active);
  border-color: var(--border-strong);
}

.composer-ctx-compact-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spin-icon {
  animation: spin 1.2s linear infinite;
}

/* ── Context Popover transition ── */
.composer-ctx-pop-enter-active,
.composer-ctx-pop-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.composer-ctx-pop-enter-from,
.composer-ctx-pop-leave-to {
  opacity: 0;
  transform: translateY(6px) scale(0.97);
}

.send-btn {
  background: var(--accent);
  color: var(--bg-app);
  border: none;
  border-radius: 10px;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: transform 0.2s ease, opacity 0.2s ease;
  flex-shrink: 0;
  margin-bottom: 2px;
}

.send-btn:hover:not(:disabled) {
  transform: scale(1.05);
}

.send-btn:active:not(:disabled) {
  transform: scale(0.95);
}

.send-btn:disabled {
  background: var(--bg-hover);
  color: var(--text-muted);
  cursor: not-allowed;
}

/* streaming 时变成红色方形 Stop 按钮 */
.send-btn.is-stop {
  background: rgba(220, 70, 70, 0.9);
  color: #fff;
  cursor: pointer;
  opacity: 1;
}
.send-btn.is-stop:hover {
  background: rgba(220, 70, 70, 1);
  transform: scale(1.05);
}
</style>
