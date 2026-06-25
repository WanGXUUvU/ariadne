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
const wStreamingPrefixTimeline = computed(() => workspace.streamingPrefixTimeline.value);
const wStreamingLatestUsage = computed(() => workspace.streamingLatestUsage.value);
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
  
  let title = '';
  const name = s.session_name;
  if (name && name !== s.session_id && !isUuid(name)) {
    title = name;
  } else if (s.last_reply_preview) {
    const preview = s.last_reply_preview.trim();
    if (preview) {
      const sentenceEnd = preview.match(/[。？！.?!]/);
      let fallbackTitle = preview;
      if (sentenceEnd && sentenceEnd.index !== undefined && sentenceEnd.index > 0) {
        fallbackTitle = preview.slice(0, sentenceEnd.index + 1);
      }
      if (fallbackTitle.length > 28) {
        fallbackTitle = fallbackTitle.slice(0, 26) + '...';
      }
      title = fallbackTitle;
    }
  }
  
  if (!title) {
    title = 'Untitled #' + s.session_id.slice(0, 8);
  }
  
  if (s.workspace_name) {
    return `[${s.workspace_name}] ${title}`;
  }
  return title;
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
  // 读取本地缓存主题并应用到 body 元素（只替换 theme-* 类，保留其他类）
  const savedTheme = localStorage.getItem('agent-build-theme') || 'default';
  document.body.classList.forEach(cls => {
    if (cls.startsWith('theme-')) document.body.classList.remove(cls);
  });
  document.body.classList.add(`theme-${savedTheme}`);
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
        <!-- 核心工作区 + 聊天面板容器 -->
        <div class="chat-area-container">
          <template v-if="wActiveSessionId">
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
              :streamingPrefixTimeline="wStreamingPrefixTimeline"
              :streamingLatestUsage="wStreamingLatestUsage"
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
          </template>

          <!-- 助理模式空态欢迎界面 -->
          <template v-else>
            <div class="assistant-launchpad">
              <div class="launchpad-grid-overlay"></div>
              <div class="launchpad-content">
                <!-- 动效 Logo -->
                <div class="assistant-logo">
                  <div class="logo-ring logo-ring-1"></div>
                  <div class="logo-ring logo-ring-2"></div>
                  <div class="logo-center">
                    <svg viewBox="0 0 24 24" width="26" height="26" stroke="url(#assistant-grad)" stroke-width="1.5" fill="none">
                      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                    </svg>
                    <svg width="0" height="0">
                      <defs>
                        <linearGradient id="assistant-grad" x1="0%" y1="0%" x2="100%" y2="100%">
                          <stop offset="0%" stop-color="var(--accent)" />
                          <stop offset="100%" stop-color="var(--accent-blue)" />
                        </linearGradient>
                      </defs>
                    </svg>
                  </div>
                </div>

                <h1 class="launchpad-title">ARIADNE // ASSISTANT</h1>
                <p class="launchpad-subtitle">
                  A general-purpose AI assistant. Ask anything, think together.
                </p>

                <!-- 快速开始按钮 -->
                <button class="assistant-start-btn" @click="workspace.createNewSession(null, null, undefined, 'assistant')">
                  <span class="btn-glow-layer"></span>
                  <span class="btn-content">
                    <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none">
                      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                    </svg>
                    New Conversation
                  </span>
                </button>

                <!-- 最近会话 -->
                <div v-if="assistantSessions.length > 0" class="recent-section">
                  <div class="section-header-mono">
                    <span class="header-line"></span>
                    <span class="header-text">RECENT CONVERSATIONS</span>
                    <span class="header-line"></span>
                  </div>
                  <div class="recent-grid">
                    <div
                      v-for="session in assistantSessions.slice(0, 4)"
                      :key="session.session_id"
                      class="recent-card"
                      @click="workspace.activeSessionId.value = session.session_id"
                    >
                      <div class="card-glow"></div>
                      <span class="card-icon">💬</span>
                      <div class="card-details">
                        <div class="card-name">{{ session.session_name || 'Untitled conversation' }}</div>
                        <div class="card-sub">{{ session.session_id.slice(0, 8) }}</div>
                      </div>
                      <span class="card-arrow">→</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </div>
        
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
      @skills-changed="workspace.loadSkills()"
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

.chat-area-container {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
  height: 100%;
}

/* ── 助理空态欢迎界面 ── */
.assistant-launchpad {
  position: relative;
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
  overflow-y: auto;
  background: transparent;
  padding: 40px 20px;
}

.launchpad-grid-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-image: radial-gradient(var(--border-dim) 1px, transparent 1px);
  background-size: 24px 24px;
  mask-image: radial-gradient(circle at center, black 30%, transparent 85%);
  -webkit-mask-image: radial-gradient(circle at center, black 30%, transparent 85%);
  pointer-events: none;
}

.launchpad-content {
  max-width: 560px;
  width: 100%;
  z-index: 5;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: 0;
}

.assistant-logo {
  position: relative;
  width: 80px;
  height: 80px;
  display: flex;
  justify-content: center;
  align-items: center;
  margin-bottom: 20px;
}

.logo-ring {
  position: absolute;
  border-radius: 50%;
  border: 1.5px solid var(--accent-subtle, rgba(255,255,255,0.08));
}

.logo-ring-1 {
  width: 70px;
  height: 70px;
  border-color: rgba(var(--accent-rgb, 255,255,255), 0.1);
}

.logo-ring-2 {
  width: 54px;
  height: 54px;
  border-color: var(--accent-subtle);
}

.logo-center {
  width: 40px;
  height: 40px;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 50%;
  background: var(--bg-elevated);
  border: 1px solid var(--border-strong);
  box-shadow: 0 0 20px var(--accent-glow);
}

@keyframes spin-clockwise {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
@keyframes spin-counter-clockwise {
  from { transform: rotate(0deg); }
  to { transform: rotate(-360deg); }
}

.launchpad-title {
  font-size: 18px;
  font-weight: 800;
  letter-spacing: 0.15em;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.launchpad-subtitle {
  font-size: 13px;
  color: var(--text-secondary);
  max-width: 380px;
  line-height: 1.6;
  margin-bottom: 28px;
}

.assistant-start-btn {
  position: relative;
  border: none;
  border-radius: 10px;
  background: var(--accent);
  color: var(--bg-app);
  font-family: var(--font-mono, monospace);
  font-size: 12px;
  font-weight: 600;
  padding: 11px 24px;
  cursor: pointer;
  box-shadow: 0 4px 16px var(--accent-glow);
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  overflow: hidden;
}

.assistant-start-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px var(--accent-glow);
  filter: brightness(1.1);
}

.assistant-start-btn:active {
  transform: translateY(0);
}

.btn-glow-layer {
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.15), transparent);
  transition: 0.5s;
}

.assistant-start-btn:hover .btn-glow-layer {
  left: 100%;
  transition: 0.7s ease-in-out;
}

.btn-content {
  display: flex;
  align-items: center;
  gap: 8px;
  position: relative;
}

.recent-section {
  width: 100%;
  max-width: 460px;
  margin-top: 32px;
}

.section-header-mono {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.header-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--border-dim), transparent);
}

.header-text {
  font-size: 9px;
  color: var(--text-muted);
  font-family: var(--font-mono, monospace);
  letter-spacing: 0.12em;
}

.recent-grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.recent-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--bg-hover);
  border: 1px solid var(--border-dim);
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s ease;
}

.recent-card:hover {
  border-color: var(--accent-glow);
  background: var(--bg-active);
  transform: translateX(3px);
}

.card-glow {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: radial-gradient(circle at 20% 50%, var(--accent-subtle), transparent 70%);
  opacity: 0;
  transition: opacity 0.2s;
  pointer-events: none;
}

.recent-card:hover .card-glow {
  opacity: 1;
}

.card-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.card-details {
  flex: 1;
  min-width: 0;
}

.card-name {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.card-sub {
  font-size: 10px;
  color: var(--text-muted);
  font-family: var(--font-mono, monospace);
  margin-top: 1px;
}

.card-arrow {
  font-size: 12px;
  color: var(--text-muted);
  transition: transform 0.2s, color 0.2s;
}

.recent-card:hover .card-arrow {
  transform: translateX(3px);
  color: var(--accent);
}
</style>

<style src="../styles/index.css"></style>
