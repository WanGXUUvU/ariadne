<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useWorkspace } from '../composables/useWorkspace';
import GlobalNav from '../components/layout/GlobalNav.vue';
import SessionSidebar from '../components/SessionSidebar.vue';
import ChatPanel from '../components/ChatPanel.vue';
import ChildAgentPanel from '../components/ChildAgentPanel.vue';
import PluginMarketplace from '../components/PluginMarketplace.vue';
import AgentManager from '../components/AgentManager.vue';
import SettingsPanel from '../components/SettingsPanel.vue';
import type { ChildAgentInfo } from '../types';

const workspace = useWorkspace();
const chatPanelRef = ref<any>(null);
const handleWithdraw = () => {
  const msg = workspace.withdrawInterruption();
  if (msg && chatPanelRef.value) {
    chatPanelRef.value.setComposerText(msg);
  }
};
const showPluginsModal = ref(false);
const showAgentsModal = ref(false);
const showSettingsModal = ref(false);

const wActiveSessionId = computed(() => workspace.activeSessionId.value);
const wActiveSession = computed(() => workspace.activeSession.value);
const wMessages = computed(() => workspace.messages.value);
const wIsChatLoading = computed(() => workspace.isChatLoading.value);
const wIsCompacting = computed(() => workspace.isCompacting.value);
const wErrorMsg = computed({
  get: () => workspace.errorMsg.value,
  set: (v) => { workspace.errorMsg.value = v; }
});
const wInfoMsg = computed({
  get: () => workspace.infoMsg.value,
  set: (v) => { workspace.infoMsg.value = v; }
});
const wAvailableAgents = computed(() => workspace.availableAgents.value);
const wActiveAgentId = computed(() => workspace.activeAgentId.value);
const wTraceRuns = computed(() => workspace.traceRuns.value);
const wIsStreaming = computed(() => workspace.isStreaming.value);
const wStreamingTimeline = computed(() => workspace.streamingTimeline.value);
const wLastCompletedRun = computed(() => workspace.lastCompletedRun.value);
const wIsAwaitingApproval = computed(() => workspace.isAwaitingApproval.value);
const wPendingApprovalInfo = computed(() => workspace.pendingApprovalInfo.value);
const wPendingApprovalInfos = computed(() => workspace.pendingApprovalInfos.value);
const wIsResolvingApproval  = computed(() => workspace.isResolvingApproval.value);
const wPermissionProfile    = computed(() => workspace.permissionProfile.value);
const wModelId           = computed(() => workspace.modelId.value);
const wModelProviderId   = computed(() => workspace.modelProviderId.value);
const wThinkingEnabled   = computed(() => workspace.thinkingEnabled.value);
const wThinkingEffort    = computed(() => workspace.thinkingEffort.value);
const wSkills            = computed(() => workspace.skills.value);
const wWorkspaces        = computed(() => workspace.workspaces.value);
const wIsInitializing    = computed(() => workspace.isInitializing.value);
const wActiveView        = computed({
  get: () => workspace.activeView.value,
  set: (v) => { workspace.activeView.value = v; }
});
const wChildAgentsBySession = computed(() => workspace.childAgentsBySession.value);
const wActiveModelContextLength = computed(() => workspace.activeModelContextLength.value);
const wCustomAgents = computed(() => workspace.customAgents.value);

// 子 Agent 标签页管理
const openChildAgents = ref<ChildAgentInfo[]>([]);
const activeChildAgentIndex = ref<number | null>(null);

// 过滤助理会话，避免编码会话溢出到助理列表
const assistantSessions = computed(() => {
  return workspace.sessions.value.filter(s => s.session_type === 'assistant');
});

// 锁死当前工作区的活跃会话类型，防止跨页面跳转时状态污染
watch([() => workspace.activeSessionId.value, () => workspace.sessions.value], () => {
  const activeSess = workspace.sessions.value.find(s => s.session_id === workspace.activeSessionId.value);
  if (activeSess && activeSess.session_type !== 'assistant') {
    const firstAssistant = workspace.sessions.value.find(s => s.session_type === 'assistant');
    workspace.activeSessionId.value = firstAssistant ? firstAssistant.session_id : null;
  }
}, { immediate: true });

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
  } else if (action === 'open-settings' || action === 'open-models') {
    showSettingsModal.value = true;
  }
};

// 打开子 Agent 对话
const handleOpenChildAgent = (info: ChildAgentInfo) => {
  // 检查是否已经打开过这个 run_id
  const existingIdx = openChildAgents.value.findIndex((a: ChildAgentInfo) => a.run_id === info.run_id);
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

const handleSelectWorkspaceDialog = async () => {
  const ws = await workspace.selectWorkspaceDialog();
  if (ws) {
    await workspace.createNewSession(ws.path, ws.name, undefined, 'assistant');
  }
};

onMounted(() => {
  workspace.initializeWorkspace();
  // 读取本地缓存主题并应用到 body 元素
  const savedTheme = localStorage.getItem('agent-build-theme') || 'default';
  document.body.className = `theme-${savedTheme}`;
});
</script>

<template>
  <div class="app-shell">
    <!-- 💡 赛博深空漂移星云：三色霓虹环境光斑 -->
    <div class="ambient-glow-blobs">
      <div class="blob blob-1"></div>
      <div class="blob blob-2"></div>
      <div class="blob blob-3"></div>
    </div>

    <div v-if="wIsInitializing" class="layout-loading" style="color: var(--text-secondary);">
      INITIALIZING WORKSPACE...
    </div>
    <div v-else class="app-layout">
      <!-- 1. Global Navigation -->
      <GlobalNav 
        v-model:activeView="wActiveView"
        @action="handleNavAction"
      />
      
      <!-- 2. Main Chat Workspace (Always visible as background) -->
      <SessionSidebar 
        :sessions="assistantSessions"
        :workspaces="wWorkspaces"
        :activeId="wActiveSessionId"
        :childAgentsBySession="wChildAgentsBySession"
        @select="(id: string) => workspace.activeSessionId.value = id"
        @new="(wsPath: string | null, wsName: string | null) => workspace.createNewSession(wsPath, wsName, undefined, 'assistant')"
        @delete="workspace.deleteSession"
        @rename="workspace.renameSession"
        @open-child-agent="handleOpenChildAgent"
        @select-workspace-dialog="handleSelectWorkspaceDialog"
      />
      
      <!-- 3. 主聊天面板 + 子 Agent 右侧面板 -->
      <div class="main-content-container">
        <ChatPanel 
          ref="chatPanelRef"
          :messages="wMessages"
          :isLoading="wIsChatLoading"
          :isCompacting="wIsCompacting"
          :error="wErrorMsg"
          :infoMsg="wInfoMsg"
          :hasSession="!!wActiveSessionId"
          :sessionTitle="sessionTitle"
          :agents="wAvailableAgents"
          :activeAgentId="wActiveAgentId"
          :traceRuns="wTraceRuns"
          :isStreaming="wIsStreaming"
          :streamingTimeline="wStreamingTimeline"
          :lastCompletedRun="wLastCompletedRun"
          :isAwaitingApproval="wIsAwaitingApproval"
          :pendingApprovalInfo="wPendingApprovalInfo"
          :pendingApprovalInfos="wPendingApprovalInfos"
          :isProcessingApproval="wIsResolvingApproval"
          :permissionProfile="wPermissionProfile"
          :contextTokens="wActiveSession?.context_tokens ?? 0"
          :contextLength="wActiveModelContextLength"
          :sessionId="wActiveSessionId"
          :modelId="wModelId"
          :providerId="wModelProviderId"
          :thinkingEnabled="wThinkingEnabled"
          :thinkingEffort="wThinkingEffort"
          :sessionLoading="wIsChatLoading"
          :skills="wSkills"
          :interruptionPendingMessage="workspace.interruptionPendingMessage.value"
          :interruptionWaitForTool="workspace.interruptionWaitForTool.value"
          @update:activeAgentId="(id: string) => workspace.activeAgentId.value = id"
          @send="(text: string, skillName?: string | null) => workspace.sendMessage(text, skillName)"
          @errorDismiss="wErrorMsg = null"
          @infoDismiss="wInfoMsg = null"
          @compact="workspace.compactSession"
          @reset="workspace.resetSession"
          @stop="workspace.stopStreaming"
          @approve="workspace.approveAction"
          @reject="workspace.rejectAction"
          @approve-all="workspace.approveAllAction"
          @update:permissionProfile="workspace.updatePermissionProfile"
          @update:model="(val: { modelId: string | null; providerId: number | null }) => workspace.updateModelConfig({ model_id: val.modelId, model_provider_id: val.providerId })"
          @update:thinkingEnabled="(val: boolean) => workspace.updateModelConfig({ thinking_enabled: val })"
          @update:thinkingEffort="(val: string) => workspace.updateModelConfig({ thinking_effort: val })"
          @retry="workspace.retryLastRun"
          @editSubmit="workspace.editAndReRun"
          @forceSend="workspace.forceInterruptAndSend"
          @withdraw="handleWithdraw"
          @discard="workspace.discardInterruption"
        />
        
        <!-- 垂直分割线 + 子 Agent 右侧面板 -->
        <template v-if="openChildAgents.length > 0">
          <div class="divider-vertical" @mousedown="startDragDivider"></div>
          <ChildAgentPanel 
            :childAgents="openChildAgents"
            :activeIndex="activeChildAgentIndex"
            :workspace="workspace"
            :style="{ width: `${childPanelWidth}px` }"
            @update:activeIndex="(idx: number) => activeChildAgentIndex = idx"
            @close="handleCloseChildAgent"
          />
        </template>
      </div>
    </div>

    <!-- Plugin Marketplace Modal -->
    <PluginMarketplace 
      :isOpen="showPluginsModal"
      :skills="wSkills"
      :error="wErrorMsg"
      @close="showPluginsModal = false"
      @toggle="workspace.toggleSkill"
      @clearError="wErrorMsg = null"
    />

    <!-- Agent Manager Modal -->
    <AgentManager
      :isOpen="showAgentsModal"
      :agents="wCustomAgents"
      @close="showAgentsModal = false"
      @save="workspace.saveAgent"
      @delete="workspace.deleteAgent"
    />

    <!-- Settings Modal -->
    <SettingsPanel
      :isOpen="showSettingsModal"
      @close="() => { showSettingsModal = false; workspace.loadEnabledModels(); }"
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

<style src="../styles/index.css"></style>
