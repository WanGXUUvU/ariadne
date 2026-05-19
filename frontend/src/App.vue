<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useWorkspace } from './composables/useWorkspace';
import GlobalNav from './components/layout/GlobalNav.vue';
import SessionSidebar from './components/SessionSidebar.vue';
import ChatPanel from './components/ChatPanel.vue';
import ChildAgentPanel from './components/ChildAgentPanel.vue';
import PluginMarketplace from './components/PluginMarketplace.vue';
import AgentManager from './components/AgentManager.vue';
import type { ChildAgentInfo } from './types';

const workspace = useWorkspace();
const showPluginsModal = ref(false);
const showAgentsModal = ref(false);

// 子 Agent 标签页管理
const openChildAgents = ref<ChildAgentInfo[]>([]);
const activeChildAgentIndex = ref<number | null>(null);

// 右侧子 Agent 面板宽度（可拖动调整）
const childPanelWidth = ref(380);
let isDraggingDivider = false;

const startDragDivider = (e: MouseEvent) => {
  isDraggingDivider = true;
  const startX = e.clientX;
  const startWidth = childPanelWidth.value;

  const handleMouseMove = (moveEvent: MouseEvent) => {
    if (!isDraggingDivider) return;
    const delta = moveEvent.clientX - startX;
    childPanelWidth.value = Math.max(260, Math.min(700, startWidth - delta));
  };

  const handleMouseUp = () => {
    isDraggingDivider = false;
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
  };

  document.addEventListener('mousemove', handleMouseMove);
  document.addEventListener('mouseup', handleMouseUp);
};

const isUuid = (s: string) => /^[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}$/i.test(s);
const sessionTitle = computed(() => {
  const s = workspace.activeSession.value;
  if (!s) return 'NEW SESSION';
  const name = s.session_name;
  if (!name || name === s.session_id || isUuid(name)) {
    return 'Untitled #' + s.session_id.slice(0, 8);
  }
  return name;
});

const handleNavAction = (action: string) => {
  if (action === 'open-plugins') {
    showPluginsModal.value = true;
  } else if (action === 'open-agents') {
    showAgentsModal.value = true;
  }
};

// 打开子 Agent 对话
const handleOpenChildAgent = (info: ChildAgentInfo) => {
  // 检查是否已经打开过这个 run_id
  const existingIdx = openChildAgents.value.findIndex(a => a.run_id === info.run_id);
  if (existingIdx >= 0) {
    // 已打开，直接切换到这个 tab
    activeChildAgentIndex.value = existingIdx;
  } else {
    // 未打开，新增 tab
    openChildAgents.value.push(info);
    activeChildAgentIndex.value = openChildAgents.value.length - 1;
  }
};

// 关闭子 Agent 标签页
const handleCloseChildAgent = (index: number) => {
  openChildAgents.value.splice(index, 1);
  if (activeChildAgentIndex.value === index) {
    // 当前 tab 被关闭，重新选择
    if (openChildAgents.value.length > 0) {
      activeChildAgentIndex.value = Math.min(index, openChildAgents.value.length - 1);
    } else {
      activeChildAgentIndex.value = null;
    }
  } else if (activeChildAgentIndex.value !== null && activeChildAgentIndex.value > index) {
    // 调整 index
    activeChildAgentIndex.value--;
  }
};

onMounted(() => {
  workspace.initializeWorkspace();
});
</script>

<template>
  <div class="app-shell">
    <div v-if="workspace.isInitializing.value" class="layout-loading" style="color: var(--text-secondary);">
      INITIALIZING WORKSPACE...
    </div>
    <div v-else class="app-layout">
      <!-- 1. Global Navigation -->
      <GlobalNav 
        v-model:activeView="workspace.activeView.value"
        @action="handleNavAction"
      />
      
      <!-- 2. Main Chat Workspace (Always visible as background) -->
      <SessionSidebar 
        :sessions="workspace.sessions.value"
        :activeId="workspace.activeSessionId.value"
        :childAgentsBySession="workspace.childAgentsBySession.value"
        @select="id => workspace.activeSessionId.value = id"
        @new="workspace.createNewSession"
        @delete="workspace.deleteSession"
        @rename="workspace.renameSession"
        @open-child-agent="handleOpenChildAgent"
      />
      
      <!-- 3. 主聊天面板 + 子 Agent 右侧面板 -->
      <div class="main-content-container">
        <ChatPanel 
          :messages="workspace.messages.value"
          :isLoading="workspace.isChatLoading.value"
          :isCompacting="workspace.isCompacting.value"
          :error="workspace.errorMsg.value"
          :infoMsg="workspace.infoMsg.value"
          :hasSession="!!workspace.activeSessionId.value"
          :sessionTitle="sessionTitle"
          :agents="workspace.availableAgents.value"
          :activeAgentId="workspace.activeAgentId.value"
          :traceRuns="workspace.traceRuns.value"
          :isStreaming="workspace.isStreaming.value"
          :streamingTimeline="workspace.streamingTimeline.value"
          :lastCompletedRun="workspace.lastCompletedRun.value"
          @update:activeAgentId="id => workspace.activeAgentId.value = id"
          @send="workspace.sendMessage"
          @errorDismiss="workspace.errorMsg.value = null"
          @infoDismiss="workspace.infoMsg.value = null"
          @compact="workspace.compactSession"
          @reset="workspace.resetSession"
          @stop="workspace.stopStreaming"
        />
        
        <!-- 垂直分割线 + 子 Agent 右侧面板 -->
        <template v-if="openChildAgents.length > 0">
          <div class="divider-vertical" @mousedown="startDragDivider"></div>
          <ChildAgentPanel 
            :childAgents="openChildAgents"
            :activeIndex="activeChildAgentIndex"
            :workspace="workspace"
            :style="{ width: `${childPanelWidth}px` }"
            @update:activeIndex="idx => activeChildAgentIndex = idx"
            @close="handleCloseChildAgent"
          />
        </template>
      </div>
    </div>

    <!-- Plugin Marketplace Modal -->
    <PluginMarketplace 
      :isOpen="showPluginsModal"
      :skills="workspace.skills.value"
      :error="workspace.errorMsg.value"
      @close="showPluginsModal = false"
      @toggle="workspace.toggleSkill"
      @clearError="workspace.errorMsg.value = null"
    />

    <!-- Agent Manager Modal -->
    <AgentManager
      :isOpen="showAgentsModal"
      :agents="workspace.customAgents.value"
      @close="showAgentsModal = false"
      @save="workspace.saveAgent"
      @delete="workspace.deleteAgent"
    />
  </div>
</template>

<style scoped>
/* 主内容容器：水平分割 ChatPanel 和 ChildAgentPanel */
.main-content-container {
  flex: 1;
  display: flex;
  flex-direction: row;
  overflow: hidden;
}

/* 垂直分割线（用于拖动调整子面板宽度） */
.divider-vertical {
  width: 4px;
  background: var(--border-dim);
  cursor: col-resize;
  transition: background 0.2s ease;
  flex-shrink: 0;
}

.divider-vertical:hover,
.divider-vertical:active {
  background: var(--accent-blue);
}
</style>

<style src="./styles/index.css"></style>
