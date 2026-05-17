<script setup lang="ts">
import { computed, ref } from 'vue';
import type { SessionSummary } from '../types';

const props = defineProps<{
  sessions: SessionSummary[];
  activeId: string | null;
}>();

const emit = defineEmits<{
  (e: 'select', id: string): void;
  (e: 'new'): void;
  (e: 'delete', id: string): void;
  (e: 'rename', id: string, name: string): void;
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
  if (!name || name === session.session_id || isUuid(name)) return null;
  return name;
};

const getSessionId = (session: SessionSummary) => {
  return '#' + session.session_id.slice(0, 8);
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
      <input v-model="searchQuery" placeholder="Filter..." class="search-input" />
    </div>

    <div class="session-list">
      <div v-if="filteredSessions.length === 0" class="session-empty">
        <svg viewBox="0 0 24 24" width="20" height="20" stroke="var(--text-muted)" stroke-width="1.5" fill="none" style="margin-bottom: 8px;">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
        </svg>
        <div class="mono-label" style="color: var(--text-muted); font-size: 10px;">NO SESSIONS YET</div>
      </div>
      <div 
        v-for="(session, idx) in filteredSessions" 
        :key="session.session_id"
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
          <div class="session-preview" v-if="session.last_reply_preview">{{ session.last_reply_preview }}</div>
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
    </div>
  </aside>
</template>

<style scoped>
.search-box {
  padding: 12px;
  border-bottom: 1px solid var(--border-dim);
  display: flex;
  align-items: center;
  gap: 8px;
}

.search-icon {
  color: var(--text-muted);
}

.search-input {
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-size: 13px;
  width: 100%;
}

.search-input::placeholder {
  color: var(--text-muted);
}

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

.session-item {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-dim);
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: var(--transition-fast);
  animation: fadeIn 0.3s ease both;
}

.session-item:hover {
  background: var(--bg-hover);
}

.session-item.active {
  background: var(--accent-subtle, rgba(255,255,255,0.06));
  border-left: 2px solid var(--accent);
  padding-left: 14px;
}

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

.session-item.active .session-title {
  color: var(--accent);
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
