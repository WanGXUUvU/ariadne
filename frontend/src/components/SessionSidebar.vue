<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue';
import type { SessionSummary, ChildAgentInfo } from '../types';

const props = defineProps<{
  sessions: SessionSummary[];
  activeId: string | null;
  childAgentsBySession?: Record<string, ChildAgentInfo[]>;
}>();

const emit = defineEmits<{
  (e: 'select', id: string): void;
  (e: 'new'): void;
  (e: 'delete', id: string): void;
  (e: 'rename', id: string, name: string): void;
  (e: 'open-child-agent', info: ChildAgentInfo): void;
}>();

const editingId = ref<string | null>(null);
const editingName = ref('');

const startEdit = (session: SessionSummary, event: MouseEvent) => {
  event.stopPropagation();
  editingId.value = session.session_id;
  editingName.value = session.session_name || '';
};

const commitEdit = (id: string) => {
  const name = editingName.value.trim();
  if (name && name !== '') {
    emit('rename', id, name);
  }
  editingId.value = null;
};

const cancelEdit = () => {
  editingId.value = null;
};

const searchQuery = ref('');
const isFocused = ref(false);
const searchInputRef = ref<HTMLInputElement | null>(null);

// 全局快捷键监听逻辑
const handleGlobalKeyDown = (e: KeyboardEvent) => {
  // 如果当前焦点已经在 input、textarea 或可编辑元素上，则不抢夺焦点（除非是快捷键操作 searchInput 本身）
  const target = e.target as HTMLElement;
  if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
    return;
  }

  // 1. 斜杠 `/` 键聚焦搜索框 (需防止输入斜杠字符)
  if (e.key === '/') {
    e.preventDefault();
    searchInputRef.value?.focus();
  }

  // 2. ⌘K 或 Ctrl+K 聚焦搜索框
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    searchInputRef.value?.focus();
  }
};

onMounted(() => {
  window.addEventListener('keydown', handleGlobalKeyDown);
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKeyDown);
});

const filteredSessions = computed(() => {
  const normalized = searchQuery.value.trim().toLowerCase();
  if (!normalized) return props.sessions;

  return props.sessions.filter((session) => {
    const title = (session.session_name || session.session_id).toLowerCase();
    return title.includes(normalized);
  });
});

const formatTime = (date: string | Date) => {
  return new Date(date).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
};

// UUID 格式检测
const isUuid = (s: string) => /^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$/i.test(s);

const getSessionTitle = (session: SessionSummary) => {
  const name = session.session_name;
  if (name && name !== session.session_id && !isUuid(name)) {
    return name;
  }
  // Try to use last reply preview or first sentence of it as fallback
  if (session.last_reply_preview) {
    const preview = session.last_reply_preview.trim();
    if (preview) {
      // Find sentence ending characters (Chinese/English)
      const sentenceEnd = preview.match(/[。？！.?!]/);
      let fallbackTitle = preview;
      if (sentenceEnd && sentenceEnd.index !== undefined && sentenceEnd.index > 0) {
        fallbackTitle = preview.slice(0, sentenceEnd.index + 1);
      }
      if (fallbackTitle.length > 28) {
        fallbackTitle = fallbackTitle.slice(0, 26) + '...';
      }
      return fallbackTitle;
    }
  }
  return null;
};

const getSessionId = (session: SessionSummary) => {
  return '#' + session.session_id.slice(0, 8);
};

// 每个子 Agent 用固定颜色（按 index 循环）
const CHILD_COLORS = ['#7c8ff7', '#f7a07c', '#7cf7b4', '#f7e07c', '#d07cf7', '#7cd4f7'];
const getChildColor = (idx: number) => CHILD_COLORS[idx % CHILD_COLORS.length];

const getChildrenForSession = (sessionId: string): ChildAgentInfo[] => {
  return props.childAgentsBySession?.[sessionId] ?? [];
};
</script>

<template>
  <aside class="session-sidebar">
    <div class="panel-header" style="flex-direction: row; gap: 8px;">
      <span class="mono-label" style="color: var(--text-primary);">SESSIONS</span>
      <button class="tech-btn" @click="$emit('new')" style="padding: 4px 8px; font-size: 12px;">
        <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
        New
      </button>
    </div>

    <div class="search-box">
      <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" class="search-icon"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
      <input 
        ref="searchInputRef" 
        v-model="searchQuery" 
        placeholder="Filter..." 
        class="search-input" 
        @focus="isFocused = true"
        @blur="isFocused = false"
      />
      <kbd class="search-kbd" :class="{ 'kbd-hide': isFocused }">⌘K</kbd>
    </div>

    <div class="session-list">
      <div v-if="filteredSessions.length === 0" class="session-empty">
        <svg viewBox="0 0 24 24" width="20" height="20" stroke="var(--text-muted)" stroke-width="1.5" fill="none" style="margin-bottom: 8px;">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
        </svg>
        <div class="mono-label" style="color: var(--text-muted); font-size: 10px;">NO SESSIONS YET</div>
      </div>
      <template
        v-for="(session, idx) in filteredSessions"
        :key="session.session_id"
      >
      <div 
        class="session-item"
        :class="{ active: activeId === session.session_id }"
        :style="{ animationDelay: `${idx * 30}ms` }"
        @click="$emit('select', session.session_id)"
      >
        <div class="session-info">
          <div class="session-title">
            <input
              v-if="editingId === session.session_id"
              class="rename-input"
              v-model="editingName"
              @blur="commitEdit(session.session_id)"
              @keyup.enter="commitEdit(session.session_id)"
              @keyup.escape="cancelEdit"
              @click.stop
              :ref="el => { if (el) (el as HTMLInputElement).focus(); }"
            />
            <template v-else>
              <span v-if="getSessionTitle(session)">{{ getSessionTitle(session) }}</span>
              <span v-else class="session-title-untitled">Untitled <span class="session-hash">{{ getSessionId(session) }}</span></span>
            </template>
          </div>
          <div class="session-meta mono-label">{{ session.message_count || 0 }} MSG &middot; {{ formatTime(session.updated_at || session.created_at) }}</div>
        </div>
        <div class="session-actions">
          <button class="rename-btn" @click.stop="startEdit(session, $event)" title="Rename">
            <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2" fill="none"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
          </button>
          <button class="delete-btn" @click.stop="$emit('delete', session.session_id)" title="Delete">
            <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2" fill="none"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
          </button>
        </div>
      </div>

      <!-- 子 Agent 列表，仅在 active session 且有子 Agent 时展示 -->
      <template v-if="activeId === session.session_id && getChildrenForSession(session.session_id).length > 0">
        <div
          v-for="(child, cidx) in getChildrenForSession(session.session_id)"
          :key="child.run_id"
          class="child-agent-item"
          @click.stop="$emit('open-child-agent', child)"
        >
          <span class="child-connector">└</span>
          <span class="child-dot" :style="{ background: getChildColor(cidx) }"></span>
          <span class="child-name" :style="{ color: getChildColor(cidx) }">{{ child.agent_name }}</span>
          <span v-if="child.status === 'running'" class="child-spinner"></span>
          <span v-else-if="child.status === 'done'" class="child-status-icon">✓</span>
          <span v-else-if="child.status === 'error'" class="child-status-icon error">✗</span>
        </div>
      </template>
      </template>
    </div>
  </aside>
</template>

<style scoped>
/* 💡 .search-box and search input scoped rules removed to let global spotlight styling in index.css take effect */

.session-list {
  flex: 1;
  overflow-y: auto;
}

.session-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 20px;
  text-align: center;
}

/* 💡 .session-item, hover and active scoped rules removed to enable high-end floating cards from index.css */

.session-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.session-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.session-meta {
  color: var(--text-muted);
}

.session-title-untitled {
  color: var(--text-muted);
  font-style: italic;
  font-weight: 400;
}
.session-hash {
  font-family: var(--font-mono, monospace);
  font-size: 11px;
  opacity: 0.6;
}
.session-preview {
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 180px;
  margin-top: 1px;
}
.session-meta {
  color: var(--text-muted);
  margin-top: 2px;
}

.session-actions {
  position: relative;
  display: flex;
  align-items: center;
  min-width: 24px;
  justify-content: flex-end;
  align-self: flex-start;
  padding-top: 2px;
}

.session-time {
  color: var(--text-muted);
  transition: opacity 0.2s;
}

.rename-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s;
  padding: 4px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.rename-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.session-item:hover .rename-btn {
  opacity: 1;
}

.delete-btn {
  background: transparent;
  border: none;
  color: var(--danger, #FF453A);
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.2s;
  padding: 4px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.delete-btn:hover {
  background: rgba(255, 69, 58, 0.1);
}

.session-item:hover .delete-btn {
  opacity: 1;
}

.rename-input {
  background: var(--bg-secondary, rgba(255,255,255,0.08));
  border: 1px solid var(--accent);
  border-radius: 4px;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 500;
  padding: 2px 6px;
  outline: none;
  width: 100%;
  box-sizing: border-box;
}

/* 💡 Active state title color override removed to let theme accent color apply */

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 子 Agent 条目 */
.child-agent-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 16px 5px 24px;
  cursor: pointer;
  font-size: 12px;
  border-bottom: 1px solid var(--border-dim);
  transition: background 0.15s;
}
.child-agent-item:hover { background: var(--bg-hover); }
.child-connector { color: var(--text-muted); font-size: 12px; }
.child-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.child-name { flex: 1; font-weight: 500; }
.child-status-icon { font-size: 11px; color: var(--text-muted); }
.child-status-icon.error { color: var(--danger, #ff453a); }

/* 转圈动画 */
@keyframes spin { to { transform: rotate(360deg); } }
.child-spinner {
  display: inline-block;
  width: 11px; height: 11px;
  border: 1.5px solid rgba(255,255,255,0.15);
  border-top-color: var(--accent, #7c8ff7);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  flex-shrink: 0;
}
.child-spinner.large { width: 20px; height: 20px; border-width: 2px; }

/* 结果弹窗 */
.child-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}
.child-modal {
  background: var(--bg-primary, #1a1a2e);
  border: 1px solid var(--border-dim);
  border-radius: 10px;
  width: 480px;
  max-width: 90vw;
  max-height: 70vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.child-modal-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-dim);
}
.child-modal-title { font-size: 14px; font-weight: 600; flex: 1; color: var(--text-primary); }
.child-modal-status {
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 10px;
  background: var(--bg-hover);
  color: var(--text-muted);
}
.child-modal-status.done { color: #7cf7b4; background: rgba(124,247,180,0.1); }
.child-modal-status.error { color: #ff453a; background: rgba(255,69,58,0.1); }
.child-modal-status.running { color: var(--accent, #7c8ff7); background: rgba(124,143,247,0.1); }
.child-modal-close {
  background: none; border: none; color: var(--text-muted);
  cursor: pointer; font-size: 14px; padding: 4px;
}
.child-modal-body {
  padding: 16px;
  overflow-y: auto;
  flex: 1;
}
.child-modal-reply {
  font-size: 13px;
  line-height: 1.7;
  color: var(--text-primary);
  white-space: pre-wrap;
}
.child-modal-error { color: var(--danger, #ff453a); font-size: 13px; }
.child-modal-running {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--text-muted);
  font-size: 13px;
}
</style>
