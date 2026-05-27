<script setup lang="ts">
const props = defineProps<{
  mode?: "coding" | "assistant";
  activeView: string;
}>();

const emit = defineEmits<{
  (e: 'update:activeView', view: string): void;
  (e: 'action', action: string): void;
}>();

const navItems = [
  { id: 'chat', type: 'view', svg: '<svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="1.5" fill="none"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line><line x1="9" y1="21" x2="9" y2="9"></line></svg>', label: 'Workspace' },
  { id: 'plugins', type: 'action', action: 'open-plugins', svg: '<svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="1.5" fill="none"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>', label: 'Plugins' },
  { id: 'agents', type: 'action', action: 'open-agents', svg: '<svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="1.5" fill="none"><circle cx="12" cy="8" r="4"></circle><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"></path><circle cx="18" cy="8" r="2.5"></circle><path d="M20.5 15c1.5.5 2.5 1.8 2.5 3.5"></path></svg>', label: 'Agents' },
  { id: 'models', type: 'action', action: 'open-models', svg: '<svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="1.5" fill="none"><rect x="2" y="2" width="20" height="8" rx="2" ry="2"></rect><rect x="2" y="14" width="20" height="8" rx="2" ry="2"></rect><line x1="6" y1="6" x2="6.01" y2="6"></line><line x1="6" y1="18" x2="6.01" y2="18"></line></svg>', label: 'Models' },
  { id: 'settings', type: 'action', action: 'open-settings', svg: '<svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="1.5" fill="none"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>', label: 'Settings' },
];

const handleClick = (item: any) => {
  if (item.type === 'view') {
    emit('update:activeView', item.id);
  } else if (item.type === 'action') {
    emit('action', item.action);
  }
};
</script>

<template>
  <nav class="global-nav">
    <div class="nav-top">
      <div class="logo">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="var(--accent)" stroke="none"><polygon points="12 2 2 22 22 22"></polygon></svg>
      </div>
    </div>
    
    <div class="nav-menu">
      <button 
        v-for="item in navItems" 
        :key="item.id"
        class="nav-item"
        :class="{ 'is-active': activeView === item.id }"
        :title="item.label"
        @click="handleClick(item)"
      >
        <span class="nav-icon" v-html="item.svg"></span>
      </button>
    </div>
    
    <div class="nav-bottom">
      <div class="user-avatar">
        <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
      </div>
    </div>
  </nav>
</template>

<style scoped>
.global-nav {
  align-items: center;
  padding: 16px 0;
  justify-content: space-between;
}

.nav-top, .nav-bottom {
  display: flex;
  justify-content: center;
}

.logo {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24px;
}

.nav-menu {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.nav-item {
  width: 100%;
  height: 48px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  transition: color 0.2s ease, background 0.2s ease;
  position: relative;
  border-radius: 8px;
  margin: 0 8px;
  width: calc(100% - 16px);
}

.nav-item:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.nav-item.is-active {
  color: var(--text-primary);
  background: var(--accent-subtle, rgba(255,255,255,0.06));
}

.nav-item.is-active::before {
  content: '';
  position: absolute;
  left: -8px;
  top: 12px;
  bottom: 12px;
  width: 2px;
  background: var(--accent);
  border-radius: 0 2px 2px 0;
  animation: navIndicator 0.2s ease;
}

@keyframes navIndicator {
  from { opacity: 0; transform: scaleY(0); }
  to { opacity: 1; transform: scaleY(1); }
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-dim);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  background: var(--bg-hover);
  transition: var(--transition-fast);
}

.user-avatar:hover {
  border-color: var(--border-strong);
}
</style>
