<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useWorkspace } from './composables/useWorkspace';
import GlobalNav from './components/layout/GlobalNav.vue';
import SessionSidebar from './components/SessionSidebar.vue';
import ChatPanel from './components/ChatPanel.vue';
import TracePanel from './components/TracePanel.vue';
import PluginMarketplace from './components/PluginMarketplace.vue';

const workspace = useWorkspace();
const showPluginsModal = ref(false);

const handleNavAction = (action: string) => {
  if (action === 'open-plugins') {
    showPluginsModal.value = true;
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
        @select="id => workspace.activeSessionId.value = id"
        @new="workspace.createNewSession"
        @delete="workspace.deleteSession"
      />
      <ChatPanel 
        :messages="workspace.messages.value"
        :isLoading="workspace.isChatLoading.value"
        :isCompacting="workspace.isCompacting.value"
        :error="workspace.errorMsg.value"
        :infoMsg="workspace.infoMsg.value"
        :hasSession="!!workspace.activeSessionId.value"
        :sessionTitle="workspace.activeSession.value?.session_name || workspace.activeSession.value?.session_id || 'NEW_SESSION'"
        :agents="workspace.availableAgents"
        :activeAgentId="workspace.activeAgentId.value"
        @update:activeAgentId="id => workspace.activeAgentId.value = id"
        @send="workspace.sendMessage"
        @errorDismiss="workspace.errorMsg.value = null"
        @infoDismiss="workspace.infoMsg.value = null"
        @compact="workspace.compactSession"
        @reset="workspace.resetSession"
      />
      <TracePanel
        :runs="workspace.traceRuns.value"
        :isLoading="workspace.isTraceLoading.value"
      />
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
  </div>
</template>

<style src="./styles/index.css"></style>
