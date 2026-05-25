<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted, watch } from 'vue';
import type { SessionSummary, ChildAgentInfo, WorkspaceSummary } from '../types';

const props = defineProps<{
  sessions: SessionSummary[];
  activeId: string | null;
  childAgentsBySession?: Record<string, ChildAgentInfo[]>;
  workspaces?: WorkspaceSummary[];
}>();

const emit = defineEmits<{
  (e: 'select', id: string): void;
  (e: 'new', workspacePath: string | null, workspaceName: string | null): void;
  (e: 'delete', id: string): void;
  (e: 'rename', id: string, name: string): void;
  (e: 'open-child-agent', info: ChildAgentInfo): void;
  (e: 'select-workspace-dialog'): void;
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
  const target = e.target as HTMLElement;
  if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) {
    return;
  }

  // 1. 斜杠 `/` 键聚焦搜索框
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

// ── 新建会话弹出框 Popover 控制 ──
const showNewSessionPopover = ref(false);
const popoverRef = ref<HTMLElement | null>(null);

const togglePopover = (event: MouseEvent) => {
  event.stopPropagation();
  showNewSessionPopover.value = !showNewSessionPopover.value;
};

const closePopover = () => {
  showNewSessionPopover.value = false;
};

const handleClickOutside = (e: MouseEvent) => {
  if (popoverRef.value && !popoverRef.value.contains(e.target as Node)) {
    closePopover();
  }
};

// ── 工作区折叠 Accordion 控制 ──
const expandedGroups = ref<Record<string, boolean>>({});

const getGroupKey = (path: string | null) => path || 'global';

const toggleGroup = (path: string | null) => {
  const key = getGroupKey(path);
  expandedGroups.value[key] = !expandedGroups.value[key];
};

onMounted(() => {
  window.addEventListener('keydown', handleGlobalKeyDown);
  window.addEventListener('click', handleClickOutside);
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKeyDown);
  window.removeEventListener('click', handleClickOutside);
});

const filteredSessions = computed(() => {
  const normalized = searchQuery.value.trim().toLowerCase();
  if (!normalized) return props.sessions;

  return props.sessions.filter((session) => {
    const title = (session.session_name || session.session_id).toLowerCase();
    return title.includes(normalized);
  });
});

// 按工作区物理分组
const groupedSessions = computed(() => {
  const groups: Record<string, { workspaceName: string; sessions: SessionSummary[] }> = {};

  filteredSessions.value.forEach((session) => {
    const wsPath = session.workspace_path || 'global';
    const wsName = session.workspace_name || '全局会话';

    if (!groups[wsPath]) {
      groups[wsPath] = {
        workspaceName: wsName,
        sessions: [],
      };
    }
    groups[wsPath].sessions.push(session);
  });

  return Object.entries(groups).map(([path, data]) => ({
    workspacePath: path === 'global' ? null : path,
    workspaceName: data.workspaceName,
    sessions: data.sessions,
  }));
});

// 监听 activeId，自动展开高亮会话所属的物理工作区折叠组
watch(
  () => props.activeId,
  (newActiveId) => {
    if (!newActiveId) return;
    const activeSession = props.sessions.find((s) => s.session_id === newActiveId);
    if (activeSession) {
      const key = getGroupKey(activeSession.workspace_path ?? null);
      expandedGroups.value[key] = true;
    }
  },
  { immediate: true }
);

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
  if (session.last_reply_preview) {
    const preview = session.last_reply_preview.trim();
    if (preview) {
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

// 每个子 Agent 用固定颜色
const CHILD_COLORS = ['#7c8ff7', '#f7a07c', '#7cf7b4', '#f7e07c', '#d07cf7', '#7cd4f7'];
const getChildColor = (idx: number) => CHILD_COLORS[idx % CHILD_COLORS.length];

const getChildrenForSession = (sessionId: string): ChildAgentInfo[] => {
  return props.childAgentsBySession?.[sessionId] ?? [];
};
</script>


<template>
  <aside class="session-sidebar">
    <!-- 1. Top Navigation: Scheduled Tasks -->
    <div class="sidebar-static-nav">
      <div class="nav-row" title="Scheduled Tasks">
        <span class="nav-row-icon">
          <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none">
            <circle cx="12" cy="12" r="10"></circle>
            <polyline points="12 6 12 12 16 14"></polyline>
          </svg>
        </span>
        <span class="nav-row-title">Scheduled Tasks</span>
      </div>
    </div>

    <!-- 2. Section Header: Projects -->
    <div class="sidebar-section-header">
      <span class="section-title">Projects</span>
      <div class="section-actions">
        <!-- View Filter Toggle Icon Button -->
        <button class="action-icon-btn" title="Toggle View Mode">
          <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2.2" fill="none">
            <line x1="4" y1="6" x2="20" y2="6"></line>
            <line x1="6" y1="12" x2="18" y2="12"></line>
            <line x1="9" y1="18" x2="15" y2="18"></line>
          </svg>
        </button>

        <!-- Folder Plus / Create Project Button with Popover -->
        <div ref="popoverRef" class="new-session-dropdown-container">
          <button class="action-icon-btn" @click="togglePopover" title="Create New Project">
            <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2.2" fill="none">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
              <line x1="12" y1="11" x2="12" y2="17"></line>
              <line x1="9" y1="14" x2="15" y2="14"></line>
            </svg>
          </button>

          <!-- Popover Menu -->
          <Transition name="popover-fade">
            <div v-if="showNewSessionPopover" class="new-session-popover">
              <div class="popover-section-title mono-label">Create Session In</div>
              
              <!-- Global Group -->
              <div class="popover-item" @click="$emit('new', null, null); closePopover();">
                <span class="popover-icon">🌐</span>
                <div class="popover-item-content">
                  <div class="popover-item-name">Default Global Workspace</div>
                  <div class="popover-item-desc">No folder isolation, full access</div>
                </div>
              </div>

              <!-- Workspace List -->
              <div v-if="workspaces && workspaces.length > 0" class="popover-section">
                <div class="popover-section-title mono-label">Recent Project Folders</div>
                <div 
                  v-for="ws in workspaces" 
                  :key="ws.id" 
                  class="popover-item"
                  @click="$emit('new', ws.path, ws.name); closePopover();"
                >
                  <span class="popover-icon">📁</span>
                  <div class="popover-item-content">
                    <div class="popover-item-name">{{ ws.name }}</div>
                    <div class="popover-item-desc" :title="ws.path">{{ ws.path }}</div>
                  </div>
                </div>
              </div>

              <div class="popover-divider"></div>

              <!-- Add Folder Button -->
              <div class="popover-item popover-action-item" @click="$emit('select-workspace-dialog'); closePopover();">
                <span class="popover-icon">➕</span>
                <div class="popover-item-content">
                  <div class="popover-item-name" style="color: var(--accent);">Register New Project Folder...</div>
                  <div class="popover-item-desc">Open macOS Finder to pick folder</div>
                </div>
              </div>
            </div>
          </Transition>
        </div>
      </div>
    </div>

    <!-- 3. Search Box -->
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
      
      <!-- ── Grouped Accordion Session List ── -->
      <template v-else>
        <div 
          v-for="group in groupedSessions" 
          :key="getGroupKey(group.workspacePath)" 
          class="workspace-group"
          :class="{ collapsed: !expandedGroups[getGroupKey(group.workspacePath)] }"
        >
          <!-- Group Folder Accordion Header (Flat style, no background/border, no inline settings/plus buttons) -->
          <div class="workspace-group-header" @click="toggleGroup(group.workspacePath)">
            <span class="folder-arrow">
              <svg viewBox="0 0 24 24" width="11" height="11" stroke="currentColor" stroke-width="2.5" fill="none"><polyline points="9 18 15 12 9 6"></polyline></svg>
            </span>
            <span class="folder-icon">
              <template v-if="group.workspacePath">
                <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2" fill="none">
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                </svg>
              </template>
              <template v-else>
                <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2" fill="none">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="2" y1="12" x2="22" y2="12"></line>
                </svg>
              </template>
            </span>
            <span class="workspace-name" :title="group.workspacePath || 'Global sessions' ">{{ group.workspaceName }}</span>
          </div>

          <!-- Group Body (Slide in and out) -->
          <Transition name="expand">
            <div v-show="expandedGroups[getGroupKey(group.workspacePath)]" class="workspace-group-body">
              <template
                v-for="(session, idx) in group.sessions"
                :key="session.session_id"
              >
                <div 
                  class="session-item"
                  :class="{ active: activeId === session.session_id }"
                  :style="{ animationDelay: `${idx * 20}ms` }"
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

                <!-- 子 Agent 列表 展示 -->
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
          </Transition>
        </div>
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

/* ── Premium Sidebar Navigation & Projects Header ── */
.sidebar-static-nav {
  padding: 14px 14px 2px 14px;
}

.nav-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  cursor: pointer;
  color: var(--text-secondary);
  transition: var(--transition-fast);
}

.nav-row:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.nav-row-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
}

.nav-row-title {
  font-size: 13px;
  font-weight: 500;
}

.sidebar-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px 6px 24px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  letter-spacing: 0.02em;
}

.section-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.action-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: transparent;
  border: none;
  color: var(--text-muted);
  border-radius: 6px;
  cursor: pointer;
  transition: var(--transition-fast);
}

.action-icon-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

/* ── Premium Accordion Workspace Groups ── */
.workspace-group {
  margin-bottom: 2px;
  border-radius: 0;
  overflow: visible;
  transition: none;
}

.workspace-group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 24px;
  background: transparent;
  border: none;
  cursor: pointer;
  user-select: none;
  transition: color 0.2s;
}

.workspace-group-header:hover {
  background: transparent;
}

.workspace-group-header:hover .workspace-name {
  color: var(--text-primary);
}

.folder-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: transform 0.25s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.collapsed .folder-arrow {
  transform: rotate(0deg);
}

.workspace-group:not(.collapsed) .folder-arrow {
  transform: rotate(90deg);
}

.folder-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent, #7c8ff7);
  opacity: 0.85;
}

.workspace-name {
  flex: 1;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  letter-spacing: normal;
  text-transform: none;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.workspace-group-body {
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  border-left: none;
  margin-left: 0;
  padding-left: 0;
}

/* Slightly indent the sessions under their parent project folder name to match premium mock exactly */
.workspace-group-body .session-item {
  margin: 2px 12px 2px 24px !important;
  padding: 8px 12px !important;
}

/* ── Premium Dropdown Popover Workspace Selector ── */
.new-session-dropdown-container {
  position: relative;
}

.dropdown-chevron {
  transition: transform 0.2s ease;
}

.dropdown-chevron.open {
  transform: rotate(180deg);
}

.new-session-popover {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  width: 280px;
  /* Translucent frosted glass blending with the active theme's elevated background */
  background: rgba(var(--bg-panel-rgb, 10, 10, 10), 0.82);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border: 1px solid var(--border-dim);
  border-radius: 12px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.18), inset 0 1px 0 rgba(255, 255, 255, 0.04);
  padding: 6px;
  z-index: 200;
  transform-origin: top right;
  overflow: hidden;
}

/* Specific translucent glassmorphism override for light themes */
body.theme-light-apple .new-session-popover,
body.theme-light-openai .new-session-popover {
  background: rgba(255, 255, 255, 0.9) !important;
  border: 1px solid rgba(0, 0, 0, 0.07);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.08);
}

.popover-section-title {
  font-size: 9px;
  font-weight: 700;
  color: var(--text-muted);
  letter-spacing: 0.08em;
  padding: 6px 12px;
  text-transform: uppercase;
}

.popover-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s, transform 0.1s;
}

.popover-item:hover {
  background: var(--bg-hover);
}

.popover-item:active {
  transform: scale(0.98);
}

.popover-icon {
  font-size: 15px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.popover-item-content {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.popover-item-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.popover-item-desc {
  font-size: 10px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.popover-divider {
  height: 1px;
  background: var(--border-dim);
  margin: 6px 4px;
}

.popover-action-item {
  background: rgba(124, 143, 247, 0.05);
  border: 1px dashed rgba(124, 143, 247, 0.2);
}

.popover-action-item:hover {
  background: rgba(124, 143, 247, 0.1);
  border-color: rgba(124, 143, 247, 0.35);
}

/* Light theme specific hover and borders adjustment inside popover for perfect clarity */
body.theme-light-apple .popover-action-item,
body.theme-light-openai .popover-action-item {
  background: rgba(96, 165, 250, 0.05) !important;
  border: 1px dashed rgba(96, 165, 250, 0.3) !important;
}

body.theme-light-apple .popover-action-item:hover,
body.theme-light-openai .popover-action-item:hover {
  background: rgba(96, 165, 250, 0.1) !important;
  border-color: rgba(96, 165, 250, 0.5) !important;
}

/* ── Transitions ── */
.popover-fade-enter-active,
.popover-fade-leave-active {
  transition: opacity 0.15s, transform 0.15s cubic-bezier(0.16, 1, 0.3, 1);
}

.popover-fade-enter-from,
.popover-fade-leave-to {
  opacity: 0;
  transform: scale(0.95) translateY(-4px);
}

/* Accordion expand/collapse transition */
.expand-enter-active,
.expand-leave-active {
  transition: grid-template-rows 0.3s ease, opacity 0.25s ease;
  display: grid;
  grid-template-rows: 1fr;
}

.expand-enter-from,
.expand-leave-to {
  grid-template-rows: 0fr;
  opacity: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.expand-enter-to,
.expand-leave-from {
  grid-template-rows: 1fr;
  opacity: 1;
}
</style>

