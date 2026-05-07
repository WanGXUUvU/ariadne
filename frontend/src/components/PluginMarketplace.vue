<script setup lang="ts">
import { ref, computed } from 'vue';
import type { SkillMetadata } from '../types';

const props = defineProps<{
  skills: SkillMetadata[];
  isOpen: boolean;
  error?: string | null;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'toggle', name: string, disabled: boolean): void;
  (e: 'clearError'): void;
}>();

const currentTab = ref<'discover' | 'manage'>('discover');
const searchQuery = ref('');

// MOCK PLUGINS for Discover tab
const mockPlugins = [
  { name: 'Computer Use', desc: 'Control Mac apps from AgentStudio', installed: false, icon: '💻' },
  { name: 'Browser Use', desc: 'Control the in-app browser with...', installed: true, icon: '🌐' },
  { name: 'Spreadsheets', desc: 'Create and edit spreadsheet files', installed: false, icon: '📊' },
  { name: 'Presentations', desc: 'Create and edit presentations', installed: false, icon: '🖼️' },
  { name: 'GitHub', desc: 'Triage PRs, issues, CI, and...', installed: false, icon: '🐙' },
  { name: 'Slack', desc: 'Read and manage Slack', installed: false, icon: '💬' },
];

const filteredMock = computed(() => {
  const norm = searchQuery.value.trim().toLowerCase();
  if (!norm) return mockPlugins;
  return mockPlugins.filter(s => s.name.toLowerCase().includes(norm));
});

const filteredRealSkills = computed(() => {
  const norm = searchQuery.value.trim().toLowerCase();
  if (!norm) return props.skills;
  return props.skills.filter(s => s.name.toLowerCase().includes(norm));
});

const getIcon = (name: string) => {
  const icons = ['📦', '⚡️', '🔧', '🌐', '📊', '🔍', '📝'];
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash += name.charCodeAt(i);
  return icons[hash % icons.length];
};
</script>

<template>
  <div v-if="isOpen" class="marketplace-modal-overlay" @click.self="$emit('close')">
    <div class="plugin-marketplace">
      <header class="marketplace-header">
        <div class="header-top">
          <div class="tabs">
            <button class="tab" :class="{ active: currentTab === 'discover' }" @click="currentTab = 'discover'">Plugins</button>
            <button class="tab" :class="{ active: currentTab === 'manage' }" @click="currentTab = 'manage'">Skills</button>
          </div>
          <div class="actions">
            <button class="tech-btn" @click="currentTab = 'manage'" style="border: none;">
              <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
              Manage
            </button>
            <button class="tech-btn" style="border: none;">
              Create
              <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><polyline points="6 9 12 15 18 9"></polyline></svg>
            </button>
            <button class="tech-btn" @click="$emit('close')" style="border: none; padding: 6px;">
              <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
          </div>
        </div>

        <div class="hero">
          <h1 class="hero-title">Make AgentStudio work your way</h1>
          
          <div class="search-wrapper">
            <div class="search-box">
              <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none" class="search-icon"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
              <input v-model="searchQuery" type="text" placeholder="Search plugins and skills..." class="hero-search" />
            </div>
            <div class="search-filters">
              <button class="tech-btn" style="border: none; height: 100%; border-left: 1px solid var(--border-dim); border-radius: 0;">
                Built by AgentStudio
                <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><polyline points="6 9 12 15 18 9"></polyline></svg>
              </button>
              <button class="tech-btn" style="border: none; height: 100%; border-left: 1px solid var(--border-dim); border-radius: 0 6px 6px 0;">
                All
                <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><polyline points="6 9 12 15 18 9"></polyline></svg>
              </button>
            </div>
          </div>
        </div>
      </header>

      <div class="marketplace-body">
        <div v-if="error" style="background: rgba(255,69,58,0.1); border: 1px solid rgba(255,69,58,0.2); color: #FF453A; padding: 12px 20px; font-size: 13px; display: flex; justify-content: space-between; font-family: var(--font-mono); margin-bottom: 24px; border-radius: var(--radius-sm);">
          <span>ERR: {{ error }}</span>
          <button style="background: transparent; border: none; color: inherit; cursor: pointer;" @click="$emit('clearError')">✕</button>
        </div>

        <h2 class="section-title mono-label">
          {{ currentTab === 'discover' ? 'FEATURED PLUGINS' : 'INSTALLED SKILLS' }}
        </h2>
        <div class="plugin-grid">
          
          <!-- DISCOVER TAB (MOCK DATA) -->
          <template v-if="currentTab === 'discover'">
            <div v-for="plugin in filteredMock" :key="plugin.name" class="plugin-card">
              <div class="plugin-icon-wrapper">
                <span class="plugin-emoji">{{ plugin.icon }}</span>
              </div>
              <div class="plugin-info">
                <h3 class="plugin-name">{{ plugin.name }}</h3>
                <p class="plugin-desc">{{ plugin.desc }}</p>
              </div>
              <button 
                class="plugin-toggle-btn"
                :class="{ installed: plugin.installed }"
                @click="plugin.installed = !plugin.installed"
                :title="!plugin.installed ? 'Install' : 'Remove'"
              >
                <svg v-if="plugin.installed" viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><polyline points="20 6 9 17 4 12"></polyline></svg>
                <svg v-else viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
              </button>
            </div>
          </template>

          <!-- MANAGE TAB (REAL DATA) -->
          <template v-if="currentTab === 'manage'">
            <div v-for="skill in filteredRealSkills" :key="skill.name" class="plugin-card" :class="{ disabled: !skill.enabled }">
              <div class="plugin-icon-wrapper">
                <span class="plugin-emoji">{{ getIcon(skill.name) }}</span>
              </div>
              <div class="plugin-info">
                <h3 class="plugin-name">{{ skill.name }}</h3>
                <p class="plugin-desc">{{ skill.description || 'Official AgentStudio extension for executing native workflows.' }}</p>
              </div>
              <button 
                class="plugin-toggle-btn"
                :class="{ installed: skill.enabled }"
                @click="$emit('toggle', skill.name, skill.enabled)"
                :title="skill.enabled ? 'Disable' : 'Enable'"
              >
                <svg v-if="skill.enabled" viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><polyline points="20 6 9 17 4 12"></polyline></svg>
                <svg v-else viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
              </button>
            </div>
          </template>

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

.plugin-marketplace {
  width: 100%;
  max-width: 1100px;
  height: 100%;
  max-height: 85vh;
  background: var(--bg-app);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-app);
  overflow-y: auto;
  color: var(--text-primary);
  box-shadow: 0 24px 64px rgba(0,0,0,0.5);
  display: flex;
  flex-direction: column;
}

.marketplace-header {
  padding: 24px 40px 60px;
  background: linear-gradient(180deg, rgba(255,255,255,0.03) 0%, transparent 100%);
  border-bottom: 1px solid var(--border-dim);
}

.header-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 60px;
}

.tabs {
  display: flex;
  gap: 24px;
}

.tab {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  padding-bottom: 8px;
  border-bottom: 2px solid transparent;
  transition: var(--transition-fast);
}

.tab:hover {
  color: var(--text-primary);
}

.tab.active {
  color: var(--text-primary);
  border-bottom-color: var(--text-primary);
}

.actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hero {
  max-width: 800px;
  margin: 0 auto;
  text-align: center;
}

.hero-title {
  font-size: 36px;
  font-weight: 600;
  letter-spacing: -0.02em;
  margin-bottom: 32px;
}

.search-wrapper {
  display: flex;
  background: var(--bg-hover);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  height: 48px;
  transition: var(--transition-fast);
}

.search-wrapper:focus-within {
  border-color: var(--accent);
  background: rgba(255,255,255,0.08);
}

.search-box {
  flex: 1;
  display: flex;
  align-items: center;
  padding: 0 16px;
  gap: 12px;
}

.search-icon {
  color: var(--text-muted);
}

.hero-search {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-size: 15px;
}

.hero-search::placeholder {
  color: var(--text-muted);
}

.search-filters {
  display: flex;
  height: 100%;
}

.marketplace-body {
  max-width: 1000px;
  margin: 0 auto;
  padding: 40px;
  flex: 1;
}

.section-title {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 24px;
  color: var(--text-primary);
}

.plugin-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.plugin-card {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  background: var(--bg-panel);
  border: 1px solid var(--border-dim);
  border-radius: var(--radius-app);
  padding: 20px;
  transition: var(--transition-fast);
}

.plugin-card:hover {
  background: var(--bg-hover);
  border-color: var(--border-strong);
}

.plugin-card.disabled {
  opacity: 0.6;
}

.plugin-icon-wrapper {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: var(--bg-app);
  border: 1px solid var(--border-strong);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  flex-shrink: 0;
}

.plugin-info {
  flex: 1;
  min-width: 0;
}

.plugin-name {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.plugin-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.plugin-toggle-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1px solid var(--border-dim);
  background: transparent;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  flex-shrink: 0;
  transition: var(--transition-fast);
}

.plugin-toggle-btn:hover {
  border-color: var(--text-primary);
  color: var(--text-primary);
}

.plugin-toggle-btn.installed {
  border-color: var(--border-strong);
  background: rgba(255,255,255,0.05);
  color: #50E3C2;
}

.plugin-toggle-btn.installed:hover {
  color: #FF453A;
  border-color: #FF453A;
  background: rgba(255,69,58,0.1);
}
</style>
