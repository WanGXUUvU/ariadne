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

const isGroupExpanded = (path: string | null) => {
  const key = getGroupKey(path);
  if (expandedGroups.value[key] !== undefined) {
    return expandedGroups.value[key];
  }
  return localStorage.getItem('settings-sidebar-folders') !== 'false';
};

const toggleGroup = (path: string | null) => {
  const key = getGroupKey(path);
  expandedGroups.value[key] = !isGroupExpanded(path);
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

interface TreeSessionItem {
  session: SessionSummary;
  depth: number;
}

// 按工作区物理分组，且组内会话结构化为树状平铺
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

  return Object.entries(groups).map(([path, data]) => {
    const sessionsList = data.sessions;
    const treeItems: TreeSessionItem[] = [];

    // 建立 ID 索引
    const sessionMap = new Map<string, SessionSummary>();
    sessionsList.forEach(s => sessionMap.set(s.session_id, s));

    // 找出所有子节点
    const childrenMap = new Map<string, SessionSummary[]>();
    sessionsList.forEach(s => {
      if (s.parent_session_id) {
        if (!childrenMap.has(s.parent_session_id)) {
          childrenMap.set(s.parent_session_id, []);
        }
        childrenMap.get(s.parent_session_id)!.push(s);
      }
    });

    // 对每个父节点的子会话进行排序 (按创建时间)
    childrenMap.forEach(list => {
      list.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
    });

    // 找到所有根节点 (无 parent_session_id，或 parent_session_id 对应的父节点不在该列表中)
    const roots = sessionsList.filter(s => {
      if (!s.parent_session_id) return true;
      return !sessionMap.has(s.parent_session_id);
    });
    // 根节点排序 (最近更新的排前面)
    roots.sort((a, b) => new Date(b.updated_at || b.created_at).getTime() - new Date(a.updated_at || a.created_at).getTime());

    // 递归进行深度优先遍历，平铺为 TreeSessionItem 数组
    const traverse = (node: SessionSummary, depth: number) => {
      treeItems.push({ session: node, depth });
      const children = childrenMap.get(node.session_id) || [];
      children.forEach(child => traverse(child, depth + 1));
    };

    roots.forEach(root => traverse(root, 0));

    return {
      workspacePath: path === 'global' ? null : path,
      workspaceName: data.workspaceName,
      treeItems,
      sessions: data.sessions,
    };
  });
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

const confirmDeleteFolder = (path: string | null, name: string, sessionsList: SessionSummary[]) => {
  if (!path) return;
  const count = sessionsList.length;
  const message = `确定要删除项目文件夹【${name}】及其下属的所有 ${count} 个会话吗？此操作将永久清除这些对话，不可逆！`;
  if (confirm(message)) {
    sessionsList.forEach(session => {
      emit('delete', session.session_id);
    });
  }
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
          :class="{ collapsed: !isGroupExpanded(group.workspacePath) }"
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
            <div class="group-actions" v-if="group.workspacePath" @click.stop>
              <button 
                class="group-action-btn plus-btn" 
                title="Create session in this folder" 
                @click.stop="$emit('new', group.workspacePath, group.workspaceName)"
              >
                <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2.2" fill="none">
                  <line x1="12" y1="5" x2="12" y2="19"></line>
                  <line x1="5" y1="12" x2="19" y2="12"></line>
                </svg>
              </button>
              <button 
                class="group-action-btn delete-folder-btn" 
                title="Delete folder and all its sessions" 
                @click.stop="confirmDeleteFolder(group.workspacePath, group.workspaceName, group.sessions)"
              >
                <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none">
                  <polyline points="3 6 5 6 21 6"></polyline>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
              </button>
            </div>
          </div>

          <!-- Group Body (Slide in and out) -->
          <Transition name="expand">
             <div v-show="isGroupExpanded(group.workspacePath)" class="workspace-group-body">
              <template
                v-for="(item, idx) in group.treeItems"
                :key="item.session.session_id"
              >
                <div 
                  class="session-item"
                  :class="{ active: activeId === item.session.session_id, 'is-branch': item.depth > 0 }"
                  :style="{ '--depth': item.depth, animationDelay: `${idx * 20}ms` }"
                  @click="$emit('select', item.session.session_id)"
                >
                  <div class="session-info">
                    <div class="session-title">
                      <input
                        v-if="editingId === item.session.session_id"
                        class="rename-input"
                        v-model="editingName"
                        @blur="commitEdit(item.session.session_id)"
                        @keyup.enter="commitEdit(item.session.session_id)"
                        @keyup.escape="cancelEdit"
                        @click.stop
                        :ref="el => { if (el) (el as HTMLInputElement).focus(); }"
                      />
                      <template v-else>
                        <span v-if="getSessionTitle(item.session)">{{ getSessionTitle(item.session) }}</span>
                        <span v-else class="session-title-untitled">Untitled <span class="session-hash">{{ getSessionId(item.session) }}</span></span>
                      </template>
                    </div>
                    <div class="session-meta mono-label">
                      <span v-if="item.session.parent_session_id" class="branch-badge">⌥ Branch</span>
                      {{ item.session.message_count || 0 }} MSG &middot; {{ formatTime(item.session.updated_at || item.session.created_at) }}
                    </div>
                  </div>
                  <div class="session-actions">
                    <button class="rename-btn" @click.stop="startEdit(item.session, $event)" title="Rename">
                      <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2" fill="none"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                    </button>
                    <button class="delete-btn" @click.stop="$emit('delete', item.session.session_id)" title="Delete">
                      <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2" fill="none"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                    </button>
                  </div>
                </div>

                <!-- 子 Agent 列表 展示 -->
                <template v-if="activeId === item.session.session_id && getChildrenForSession(item.session.session_id).length > 0">
                  <div
                    v-for="(child, cidx) in getChildrenForSession(item.session.session_id)"
                    :key="child.run_id"
                    class="child-agent-item"
                    :style="{ paddingLeft: `${24 + item.depth * 16}px` }"
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
  padding: 8px 16px;
  background: transparent;
  border: none;
  cursor: pointer;
  user-select: none;
  transition: color 0.2s, background 0.2s ease;
  border-radius: 6px;
  margin: 0 8px;
}

.workspace-group-header:hover {
  background: var(--bg-hover);
}

.workspace-group-header:hover .workspace-name {
  color: var(--text-primary);
}

.group-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s ease;
}

.workspace-group-header:hover .group-actions {
  opacity: 1;
}

.group-action-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}

.group-action-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.group-action-btn.delete-folder-btn {
  color: var(--danger, #FF453A);
}

.group-action-btn.delete-folder-btn:hover {
  background: rgba(255, 69, 58, 0.15);
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
  margin: 2px 12px 2px calc(24px + var(--depth, 0) * 16px) !important;
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

/* ── Tree Branch Connectors & Badges ── */
.session-item.is-branch {
  position: relative;
}

.session-item.is-branch::before {
  content: "";
  position: absolute;
  left: -12px;
  top: -12px;
  width: 12px;
  height: 26px;
  border-left: 1.5px solid var(--border-strong, rgba(255, 255, 255, 0.15));
  border-bottom: 1.5px solid var(--border-strong, rgba(255, 255, 255, 0.15));
  border-bottom-left-radius: 6px;
  pointer-events: none;
  transition: border-color 0.2s ease, opacity 0.2s ease;
}

.session-item.is-branch:hover::before {
  border-color: var(--accent, #7c8ff7);
}

.session-item.is-branch.active::before {
  border-color: var(--accent, #7c8ff7);
}

/* Light theme specific connectors adjustment */
body.theme-light-apple .session-item.is-branch::before,
body.theme-light-openai .session-item.is-branch::before {
  border-left-color: rgba(0, 0, 0, 0.08);
  border-bottom-color: rgba(0, 0, 0, 0.08);
}

.branch-badge {
  background: rgba(124, 143, 247, 0.08);
  color: var(--accent, #7c8ff7);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 9px;
  margin-right: 4px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}
</style>

