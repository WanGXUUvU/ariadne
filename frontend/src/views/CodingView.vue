<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useWorkspace } from '../composables/useWorkspace';
import GlobalNav from '../components/layout/GlobalNav.vue';
import SessionSidebar from '../components/SessionSidebar.vue';
import ChatPanel from '../components/ChatPanel.vue';
import ChildAgentPanel from '../components/ChildAgentPanel.vue';
import PluginMarketplace from '../components/PluginMarketplace.vue';
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

// 过滤开发项目会话，确保开发侧边栏只显示 coding 会话
const codingSessions = computed(() => {
  return workspace.sessions.value.filter(s => s.session_type === 'coding');
});

// 锁死当前开发视窗活跃会话，防止从个人助理返回时会话状态错乱
watch([() => workspace.activeSessionId.value, () => workspace.sessions.value], () => {
  const activeSess = workspace.sessions.value.find(s => s.session_id === workspace.activeSessionId.value);
  if (activeSess && activeSess.session_type !== 'coding') {
    const firstCoding = workspace.sessions.value.find(s => s.session_type === 'coding');
    workspace.activeSessionId.value = firstCoding ? firstCoding.session_id : null;
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
    await workspace.createNewSession(ws.path, ws.name, undefined, 'coding');
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
        :sessions="codingSessions"
        :workspaces="wWorkspaces"
        :activeId="wActiveSessionId"
        :childAgentsBySession="wChildAgentsBySession"
        @select="(id: string) => workspace.activeSessionId.value = id"
        @new="(wsPath: string | null, wsName: string | null) => workspace.createNewSession(wsPath, wsName, undefined, 'coding')"
        @delete="workspace.deleteSession"
        @rename="workspace.renameSession"
        @open-child-agent="handleOpenChildAgent"
        @select-workspace-dialog="handleSelectWorkspaceDialog"
      />
      
      <!-- 3. 主聊天面板 + 子 Agent 右侧面板 -->
      <div class="main-content-container">
        <!-- 核心工作区绑定 + 聊天面板容器 -->
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
              @approveAll="workspace.approveAllAction"
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

          <!-- 💡 终极高定：Code Studio Launchpad 仪表盘空态 -->
          <template v-else>
            <div class="studio-launchpad">
              <div class="launchpad-grid-overlay"></div>
              
              <div class="launchpad-content">
                <!-- 顶级动效 Logo -->
                <div class="cyber-core-logo">
                  <div class="core-ring core-ring-1"></div>
                  <div class="core-ring core-ring-2"></div>
                  <div class="core-center">
                    <svg viewBox="0 0 24 24" width="28" height="28" stroke="url(#cyan-green-grad)" stroke-width="1.5" fill="none" class="core-svg">
                      <polyline points="16 18 22 12 16 6"></polyline>
                      <polyline points="8 6 2 12 8 18"></polyline>
                    </svg>
                    <svg width="0" height="0">
                      <defs>
                        <linearGradient id="cyan-green-grad" x1="0%" y1="0%" x2="100%" y2="100%">
                          <stop offset="0%" stop-color="#10b981" />
                          <stop offset="100%" stop-color="#06b6d4" />
                        </linearGradient>
                      </defs>
                    </svg>
                  </div>
                </div>

                <h1 class="launchpad-title">ANTIGRAVITY // CODE ENGINE</h1>
                <p class="launchpad-subtitle">
                  A high-isolation, autonomous multi-agent developer system.
                </p>

                <!-- 系统状态指示器面板 -->
                <div class="system-status-panel">
                  <div class="status-indicator">
                    <span class="indicator-dot green-pulsing"></span>
                    <div class="indicator-text">
                      <div class="indicator-label">SANDBOX PROTECTION</div>
                      <div class="indicator-value font-mono">FULLY ENFORCED</div>
                    </div>
                  </div>
                  <div class="status-indicator">
                    <span class="indicator-dot cyan-pulsing"></span>
                    <div class="indicator-text">
                      <div class="indicator-label">ACTIVE MENTAL PROFILE</div>
                      <div class="indicator-value font-mono">SOFTWARE ENGINEER</div>
                    </div>
                  </div>
                  <div class="status-indicator">
                    <span class="indicator-dot purple-pulsing"></span>
                    <div class="indicator-text">
                      <div class="indicator-label">LOCAL RULES ENGINE</div>
                      <div class="indicator-value font-mono">AGENTS.MD SYNCHRONIZED</div>
                    </div>
                  </div>
                </div>

                <!-- 大尺寸快捷绑定工作区按钮 -->
                <button class="primary-bind-btn" @click="handleSelectWorkspaceDialog">
                  <span class="btn-glow-layer"></span>
                  <span class="btn-content">
                    <span class="btn-icon">📁</span>
                    Connect New Project Folder
                  </span>
                </button>

                <!-- 最近打开的项目文件夹列表 -->
                <div class="recent-workspaces-section">
                  <div class="section-header-mono">
                    <span class="header-line"></span>
                    <span class="header-text">RECENT PROJECTS</span>
                    <span class="header-line"></span>
                  </div>

                  <div v-if="wWorkspaces.length > 0" class="recent-ws-grid">
                    <div 
                      v-for="ws in wWorkspaces.slice(0, 4)" 
                      :key="ws.id" 
                      class="recent-ws-card"
                      @click="workspace.createNewSession(ws.path, ws.name, undefined, 'coding')"
                    >
                      <div class="ws-card-glow"></div>
                      <span class="ws-card-icon">📁</span>
                      <div class="ws-card-details">
                        <div class="ws-card-name">{{ ws.name }}</div>
                        <div class="ws-card-path" :title="ws.path">{{ ws.path }}</div>
                      </div>
                      <span class="ws-card-arrow">→</span>
                    </div>
                  </div>
                  <div v-else class="recent-ws-empty font-mono">
                    No registered workspaces yet. Click the button above to bind a directory.
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

.workspace-binding-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 20px;
  background: rgba(var(--bg-panel-rgb, 10, 10, 10), 0.5);
  border-bottom: 1px solid var(--border-dim);
  font-family: var(--font-mono, monospace);
  font-size: 11px;
}

.workspace-binding-bar.has-workspace {
  background: rgba(16, 185, 129, 0.05); /* subtle emerald green glow */
  border-bottom: 1px solid rgba(16, 185, 129, 0.15);
}

.workspace-bar-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.workspace-icon {
  font-size: 14px;
}

.workspace-title-label {
  color: var(--text-muted);
}

.workspace-name-highlight {
  color: var(--accent);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workspace-path-mute {
  font-weight: normal;
  color: var(--text-muted);
  font-size: 10px;
}

.workspace-name-warn {
  color: var(--warning, #f5a623);
  font-weight: 500;
}

.workspace-bar-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.glowing-sandbox-pill {
  font-size: 9px;
  font-weight: bold;
  letter-spacing: 0.05em;
  color: #10b981;
  background: rgba(16, 185, 129, 0.1);
  padding: 2px 6px;
  border-radius: 99px;
  border: 1px solid rgba(16, 185, 129, 0.2);
  box-shadow: 0 0 8px rgba(16, 185, 129, 0.15);
}

.ws-action-btn {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  color: var(--text-secondary);
  font-size: 10px;
  font-family: var(--font-mono, monospace);
  padding: 3px 8px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.ws-action-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.15);
  color: var(--text-primary);
}

/* 🎨 终极高定：Code Studio Launchpad 仪表盘样式 */
.studio-launchpad {
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
  max-width: 640px;
  width: 100%;
  z-index: 5;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

/* 🌀 赛博旋转 Logo */
.cyber-core-logo {
  position: relative;
  width: 90px;
  height: 90px;
  display: flex;
  justify-content: center;
  align-items: center;
  margin-bottom: 20px;
}

.core-ring {
  position: absolute;
  border-radius: 50%;
  border: 1.5px solid rgba(16, 185, 129, 0.12);
}

.core-ring-1 {
  width: 80px;
  height: 80px;
}

.core-ring-2 {
  width: 60px;
  height: 60px;
  border-color: rgba(6, 182, 212, 0.2);
}

.core-center {
  width: 44px;
  height: 44px;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 50%;
  background: var(--bg-elevated);
  border: 1px solid rgba(16, 185, 129, 0.35);
  box-shadow: 0 0 20px rgba(16, 185, 129, 0.15);
  transition: all 0.3s ease;
}

.cyber-core-logo:hover .core-center {
  border-color: rgba(6, 182, 212, 0.5);
  box-shadow: 0 0 25px rgba(6, 182, 212, 0.3);
  transform: scale(1.05);
}

.core-svg {
  filter: drop-shadow(0 0 4px rgba(16, 185, 129, 0.4));
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
  font-size: 20px;
  font-weight: 800;
  letter-spacing: 0.15em;
  color: var(--text-primary);
  margin-bottom: 6px;
  text-shadow: 0 0 24px rgba(6, 182, 212, 0.12);
}

.launchpad-subtitle {
  font-size: 13px;
  color: var(--text-secondary);
  max-width: 400px;
  line-height: 1.6;
  margin-bottom: 28px;
}

/* 📊 状态面板 */
.system-status-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 32px;
  justify-content: center;
  width: 100%;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  background: var(--bg-hover);
  border: 1px solid var(--border-dim);
  border-radius: 10px;
}

.indicator-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.green-pulsing {
  background: #10b981;
  box-shadow: 0 0 8px #10b981;
}

.cyan-pulsing {
  background: #06b6d4;
  box-shadow: 0 0 8px #06b6d4;
}

.purple-pulsing {
  background: #a855f7;
  box-shadow: 0 0 8px #a855f7;
}

@keyframes status-pulse {
  0% { opacity: 0.4; }
  50% { opacity: 1; }
  100% { opacity: 0.4; }
}

.indicator-text {
  display: flex;
  flex-direction: column;
  text-align: left;
}

.indicator-label {
  font-size: 8px;
  color: var(--text-muted);
  font-weight: 700;
  letter-spacing: 0.05em;
}

.indicator-value {
  font-size: 10px;
  color: var(--text-secondary);
  font-weight: 600;
  margin-top: 1px;
}

/* 🚀 快捷连接大按钮 */
.primary-bind-btn {
  position: relative;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #10b981, #06b6d4);
  color: #ffffff;
  font-family: var(--font-mono, monospace);
  font-size: 12px;
  font-weight: 600;
  padding: 12px 28px;
  cursor: pointer;
  box-shadow: 0 4px 16px rgba(6, 182, 212, 0.2);
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  overflow: hidden;
}

.primary-bind-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(6, 182, 212, 0.3);
}

.primary-bind-btn:active {
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

.primary-bind-btn:hover .btn-glow-layer {
  left: 100%;
  transition: 0.7s ease-in-out;
}

.btn-content {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 📁 最近打开的项目列表 */
.recent-workspaces-section {
  width: 100%;
  max-width: 500px;
  margin-top: 36px;
}

.section-header-mono {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
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

.recent-ws-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.recent-ws-card {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.015);
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 8px;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s ease;
}

.recent-ws-card:hover {
  border-color: rgba(6, 182, 212, 0.25);
  background: rgba(255, 255, 255, 0.03);
  transform: translateX(3px);
}

.ws-card-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.ws-card-details {
  flex: 1;
  min-width: 0;
}

.ws-card-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.ws-card-path {
  font-size: 10px;
  color: var(--text-muted);
  font-family: var(--font-mono, monospace);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-top: 1px;
}

.ws-card-arrow {
  font-size: 12px;
  color: var(--text-muted);
  transition: transform 0.2s;
}

.recent-ws-card:hover .ws-card-arrow {
  transform: translateX(3px);
  color: var(--accent);
}

.recent-ws-empty {
  font-size: 10px;
  color: var(--text-muted);
  padding: 16px;
  background: rgba(255, 255, 255, 0.01);
  border: 1px dashed rgba(255, 255, 255, 0.05);
  border-radius: 8px;
}
</style>

<style src="../styles/index.css"></style>
