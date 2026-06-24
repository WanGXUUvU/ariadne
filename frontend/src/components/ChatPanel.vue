<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue';
import type { AgentMessage, TraceRunSummary, ApprovalInfo, SkillMetadata } from '../types';
import type { UiAgentOption } from '../types/ui';
import MessageList from './MessageList.vue';
import MessageComposer from './MessageComposer.vue';

const props = defineProps<{
  messages: AgentMessage[];
  isLoading: boolean;
  isCompacting: boolean;
  error: string | null;
  infoMsg: string | null;
  hasSession: boolean;
  sessionTitle: string;
  agents: UiAgentOption[];
  activeAgentId: string;
  traceRuns?: TraceRunSummary[];
  isStreaming?: boolean;
  streamingTimeline?: import('../types').StreamingItem[];
  streamingPrefixTimeline?: import('../types').StreamingItem[];
  lastCompletedRun?: TraceRunSummary | null;
  isAwaitingApproval?: boolean;
  pendingApprovalInfo?: ApprovalInfo | null;
  pendingApprovalInfos?: ApprovalInfo[];
  isProcessingApproval?: boolean;
  permissionProfile?: string;
  /** 当前已使用的 token 数（来自 session.context_tokens） */
  contextTokens?: number;
  /** 模型最大上下文长度（来自选中模型的 context_length） */
  contextLength?: number;
  sessionId: string | null;
  modelId: string | null;
  providerId: number | null;
  thinkingEnabled: boolean;
  thinkingEffort: string;
  /** 当前 session 详情正在加载中 */
  sessionLoading?: boolean;
  /** 已加载的 skill 列表，用于斜杠命令菜单 */
  skills?: SkillMetadata[];
  interruptionPendingMessage?: string | null;
  interruptionWaitForTool?: boolean;
}>();

const emit = defineEmits<{
  (e: 'send', text: string, skillName?: string | null): void;
  (e: 'errorDismiss'): void;
  (e: 'infoDismiss'): void;
  (e: 'update:activeAgentId', id: string): void;
  (e: 'compact'): void;
  (e: 'reset'): void;
  (e: 'stop'): void;
  (e: 'approve', approvalId?: string): void;
  (e: 'reject', approvalId?: string): void;
  (e: 'approveAll'): void;
  (e: 'update:permissionProfile', profile: string): void;
  (e: 'update:model', val: { modelId: string | null; providerId: number | null }): void;
  (e: 'update:thinkingEnabled', val: boolean): void;
  (e: 'update:thinkingEffort', val: string): void;
  (e: 'retry'): void;
  (e: 'editSubmit', index: number, content: string): void;
  (e: 'forceSend'): void;
  (e: 'withdraw'): void;
  (e: 'discard'): void;
}>();

const agentDropdownOpen = ref(false);
const agentSelectorRef = ref<HTMLElement | null>(null);

const activeAgentName = computed(() => props.agents.find(a => a.id === props.activeAgentId)?.name ?? props.activeAgentId);
const selectAgent = (id: string) => {
  emit('update:activeAgentId', id);
  agentDropdownOpen.value = false;
};

const handleOutsideClick = (e: MouseEvent) => {
  if (agentSelectorRef.value && !agentSelectorRef.value.contains(e.target as Node)) {
    agentDropdownOpen.value = false;
  }
};
onMounted(() => document.addEventListener('mousedown', handleOutsideClick));
onUnmounted(() => document.removeEventListener('mousedown', handleOutsideClick));

const handleReset = () => {
  if (confirm('Reset this session? This will clear all chat history.')) {
    emit('reset');
  }
};

const composerRef = ref<any>(null);
const setComposerText = (val: string) => {
  if (composerRef.value) {
    composerRef.value.setText(val);
  }
};

defineExpose({
  setComposerText,
});
</script>

<template>
  <main v-if="!hasSession" class="chat-panel empty-state">
    <div class="empty-card">
      <div class="empty-icon">
        <svg viewBox="0 0 24 24" width="28" height="28" stroke="currentColor" stroke-width="1" fill="none">
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
        </svg>
      </div>
      <div class="empty-title">No session selected</div>
      <p class="empty-desc">Choose a session from the sidebar, or create a new one to get started.</p>
    </div>
  </main>

  <main v-else class="chat-panel">
    <header class="panel-header">
      <!-- 左侧：会话标题 + 状态 -->
      <div class="header-left">
        <span class="session-label">{{ sessionTitle }}</span>
        <div class="status-pill" :class="{ active: isLoading || isStreaming }">
          <span class="status-dot"></span>
          <span class="status-text">{{ (isLoading || isStreaming) ? 'running' : 'idle' }}</span>
        </div>
      </div>

      <!-- 右侧：Agent 选择 + 操作 -->
      <div class="header-right">
        <!-- 自定义 Agent 选择器 -->
        <div class="agent-selector" ref="agentSelectorRef">
          <button class="agent-trigger" @click="agentDropdownOpen = !agentDropdownOpen" :class="{ open: agentDropdownOpen }">
            <span class="agent-dot"></span>
            <span class="agent-name">{{ activeAgentName }}</span>
            <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none" class="agent-chevron" :class="{ open: agentDropdownOpen }"><polyline points="6 9 12 15 18 9"></polyline></svg>
          </button>
          <Transition name="dropdown">
            <div v-if="agentDropdownOpen" class="agent-dropdown">
              <button
                v-for="agent in agents"
                :key="agent.id"
                class="agent-option"
                :class="{ selected: agent.id === activeAgentId }"
                @click="selectAgent(agent.id)"
              >
                <span class="agent-opt-check">
                  <svg v-if="agent.id === activeAgentId" viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2.5" fill="none"><polyline points="20 6 9 17 4 12"></polyline></svg>
                </span>
                {{ agent.name }}
              </button>
            </div>
          </Transition>
        </div>

        <div class="header-divider"></div>



        <button class="icon-btn danger" @click="handleReset" title="Reset session">
          <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><polyline points="1 4 1 10 7 10"></polyline><path d="M3.51 15a9 9 0 1 0 .49-4.95"></path></svg>
        </button>
      </div>
    </header>

    <!-- 错误条 -->
    <div v-if="error" class="notice-bar error-bar">
      <span>{{ error }}</span>
      <button class="notice-close" @click="$emit('errorDismiss')">✕</button>
    </div>

    <!-- 信息条 -->
    <div v-if="infoMsg" class="notice-bar info-bar">
      <span>{{ infoMsg }}</span>
      <button class="notice-close" @click="$emit('infoDismiss')">✕</button>
    </div>

    <MessageList
      :messages="messages"
      :isLoading="isLoading"
      :isCompacting="isCompacting"
      :traceRuns="traceRuns"
      :isStreaming="isStreaming"
      :streamingTimeline="streamingTimeline"
      :streamingPrefixTimeline="streamingPrefixTimeline"
      :lastCompletedRun="lastCompletedRun"
      :error="error"
      :isAwaitingApproval="isAwaitingApproval"
      :pendingApprovalInfo="pendingApprovalInfo"
      :pendingApprovalInfos="pendingApprovalInfos"
      :isProcessingApproval="isProcessingApproval"
      @approve="$emit('approve', $event)"
      @reject="$emit('reject', $event)"
      @approve-all="$emit('approveAll')"
      @retry="$emit('retry')"
      @edit-submit="(index, content) => $emit('editSubmit', index, content)"
    />

    <!-- 悬浮挂起排队提示横幅 (Premium glassmorphic pending-interruption banner with 3 icon actions) -->
    <Transition name="slide-fade">
      <div v-if="interruptionPendingMessage" class="interruption-pending-banner">
        <div class="banner-glass-container">
          <div class="banner-info">
            <span class="banner-icon">⚡</span>
            <div class="banner-text">
              <div class="banner-title">智能体工具执行中</div>
              <div class="banner-subtitle">您的输入已加入队列，将在工具执行完毕后自动发送：</div>
              <div class="banner-preview">“{{ interruptionPendingMessage }}”</div>
            </div>
          </div>
          <div class="banner-actions">
            <!-- 向上发送箭头 (直接发送并打断) -->
            <button class="tech-btn icon-action-btn success" @click="emit('forceSend')" title="直接发送并打断当前工具">
              <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2.5" fill="none">
                <line x1="12" y1="19" x2="12" y2="5"></line>
                <polyline points="5 12 12 5 19 12"></polyline>
              </svg>
            </button>
            <!-- 向下撤回箭头 (撤回到输入框编辑) -->
            <button class="tech-btn icon-action-btn secondary" @click="emit('withdraw')" title="撤回当前消息到输入框编辑">
              <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2.5" fill="none">
                <line x1="12" y1="5" x2="12" y2="19"></line>
                <polyline points="19 12 12 19 5 12"></polyline>
              </svg>
            </button>
            <!-- 垃圾桶 (直接删除此挂起消息，不影响当前流程) -->
            <button class="tech-btn icon-action-btn danger" @click="emit('discard')" title="删除挂起消息（不影响当前运行）">
              <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </Transition>

    <MessageComposer
      ref="composerRef"
      :disabled="isLoading || isCompacting"
      :messageCount="messages.length"
      :isStreaming="isStreaming"
      :permissionProfile="permissionProfile"
      :sessionId="sessionId"
      :modelId="modelId"
      :providerId="providerId"
      :thinkingEnabled="thinkingEnabled"
      :thinkingEffort="thinkingEffort"
      :sessionLoading="sessionLoading"
      :contextTokens="contextTokens"
      :contextLength="contextLength"
      :isCompacting="isCompacting"
      :skills="skills ?? []"
      @send="(text, skillName) => $emit('send', text, skillName)"
      @stop="$emit('stop')"
      @update:permissionProfile="$emit('update:permissionProfile', $event)"
      @update:model="$emit('update:model', $event)"
      @update:thinkingEnabled="$emit('update:thinkingEnabled', $event)"
      @update:thinkingEffort="$emit('update:thinkingEffort', $event)"
      @compact="$emit('compact')"
    />
  </main>
</template>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: transparent !important;
  position: relative;
}

/* ---- 空态 ---- */
.chat-panel.empty-state {
  align-items: center;
  justify-content: center;
}
.empty-card {
  text-align: center;
  max-width: 320px;
  padding: 40px 32px;
  border: 1px solid var(--border-dim);
  border-radius: 16px;
  background: var(--bg-elevated);
}
.empty-icon {
  display: flex;
  justify-content: center;
  color: var(--text-muted);
  margin-bottom: 16px;
}
.empty-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}
.empty-desc {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

/* ---- 顶栏 ---- */
.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 20px;
  border-bottom: 1px solid var(--border-dim);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  /* 💡 顶级设计：半透明，完美穿透流动星云，随极客主题底色自适应变色 */
  background: rgba(var(--bg-panel-rgb, 10, 10, 10), 0.4) !important;
  position: sticky;
  top: 0;
  z-index: 20;
  gap: 12px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}
.session-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 260px;
}

.status-pill {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 3px 8px;
  border-radius: 99px;
  background: var(--bg-hover);
  border: 1px solid var(--border-dim);
  flex-shrink: 0;
}
.status-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--text-muted);
  transition: background 0.3s;
}
.status-pill.active .status-dot {
  background: #F5A623;
  box-shadow: 0 0 6px #F5A623;
  animation: pulse-dot 1.2s ease-in-out infinite;
}
.status-text {
  font-family: var(--font-mono, monospace);
  font-size: 10px;
  color: var(--text-muted);
  letter-spacing: 0.05em;
}

.stop-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: 99px;
  background: rgba(220, 80, 80, 0.15);
  border: 1px solid rgba(220, 80, 80, 0.4);
  color: #e06060;
  font-family: var(--font-mono, monospace);
  font-size: 10px;
  letter-spacing: 0.05em;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}
.stop-btn:hover {
  background: rgba(220, 80, 80, 0.28);
  border-color: rgba(220, 80, 80, 0.7);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.header-divider {
  width: 1px;
  height: 16px;
  background: var(--border-dim);
  margin: 0 4px;
}

/* ---- Agent 选择器 ---- */
.agent-selector {
  position: relative;
}
.agent-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  background: var(--bg-hover);
  border: 1px solid var(--border-dim);
  border-radius: 8px;
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 12px;
  transition: background 0.15s, border-color 0.15s;
}
.agent-trigger:hover, .agent-trigger.open {
  background: var(--bg-active);
  border-color: var(--border-strong);
  color: var(--text-primary);
}
.agent-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  flex-shrink: 0;
}
.agent-name {
  font-family: var(--font-mono, monospace);
  font-size: 11px;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.agent-chevron {
  transition: transform 0.2s;
  flex-shrink: 0;
}
.agent-chevron.open { transform: rotate(180deg); }

.agent-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  min-width: 200px;
  /* 💡 磨砂半透明高阶材质，配合光晕阴影 */
  background: var(--bg-panel);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid var(--border-strong);
  border-radius: 10px;
  padding: 4px;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.4), var(--shadow-glow);
  z-index: 100;
}
.agent-option {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  background: transparent;
  border: none;
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  text-align: left;
  transition: background 0.1s, color 0.1s;
}
.agent-option:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}
.agent-option.selected {
  color: var(--text-primary);
}
.agent-opt-check {
  width: 16px;
  color: var(--accent);
  flex-shrink: 0;
}

/* dropdown 动画 */
.dropdown-enter-active, .dropdown-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.dropdown-enter-from, .dropdown-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.97);
}

/* ---- 图标按钮 ---- */
.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  background: var(--bg-hover);
  border: 1px solid var(--border-dim);
  border-radius: 8px;
  cursor: pointer;
  color: var(--text-secondary);
  transition: background 0.15s, color 0.15s;
}
.icon-btn:hover {
  background: var(--bg-active);
  color: var(--text-primary);
}
.icon-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.icon-btn.danger { color: var(--danger, #FF453A); border-color: rgba(255,69,58,0.2); }
.icon-btn.danger:hover { background: rgba(255,69,58,0.1); border-color: rgba(255,69,58,0.4); }

/* ---- 通知条 ---- */
.notice-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 20px;
  font-size: 13px;
  font-family: var(--font-mono, monospace);
  border-bottom: 1px solid transparent;
}
.error-bar {
  background: rgba(255,69,58,0.08);
  border-color: rgba(255,69,58,0.2);
  color: #FF6B6B;
}
.info-bar {
  background: rgba(80,227,194,0.06);
  border-color: rgba(80,227,194,0.15);
  color: #50E3C2;
}
.notice-close {
  background: transparent;
  border: none;
  color: inherit;
  cursor: pointer;
  opacity: 0.6;
  font-size: 14px;
  padding: 2px 6px;
  border-radius: 4px;
}
.notice-close:hover { opacity: 1; }


/* ---- 挂起打断提示横幅 ---- */
.interruption-pending-banner {
  margin: 10px 16px 4px 16px;
}

.banner-glass-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 12px 18px;
  background: rgba(30, 30, 45, 0.85);
  backdrop-filter: blur(20px) saturate(160%);
  border: 1px dashed var(--accent-subtle, rgba(124, 143, 247, 0.35));
  border-radius: 12px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
  animation: pulse-border-accent 3s infinite alternate;
}

@keyframes pulse-border-accent {
  from { border-color: rgba(124, 143, 247, 0.25); }
  to { border-color: rgba(124, 143, 247, 0.6); }
}

body.theme-light-apple .banner-glass-container,
body.theme-light-openai .banner-glass-container {
  background: rgba(250, 250, 252, 0.92) !important;
  border-color: rgba(0, 0, 0, 0.12);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.08);
}

.banner-info {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  min-width: 0;
}

.banner-icon {
  font-size: 16px;
  color: var(--accent);
  margin-top: 1px;
  animation: bounce-spark 2.5s infinite alternate;
}

@keyframes bounce-spark {
  from { transform: translateY(0); }
  to { transform: translateY(-2px); }
}

.banner-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.banner-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.banner-subtitle {
  font-size: 11px;
  color: var(--text-muted);
}

.banner-preview {
  font-size: 11.5px;
  font-style: italic;
  font-family: var(--font-mono, monospace);
  color: var(--accent);
  background: rgba(124, 143, 247, 0.04);
  padding: 2px 6px;
  border-radius: 4px;
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.banner-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.tech-btn.icon-action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border-dim);
  color: var(--text-secondary);
}

.tech-btn.icon-action-btn:hover {
  transform: translateY(-0.5px);
  color: var(--text-primary);
}

.tech-btn.icon-action-btn.success:hover {
  background: rgba(46, 204, 113, 0.15) !important;
  border-color: rgba(46, 204, 113, 0.4) !important;
  color: #2ecc71 !important;
}

.tech-btn.icon-action-btn.secondary:hover {
  background: rgba(255, 255, 255, 0.08) !important;
  border-color: var(--border-strong) !important;
}

.tech-btn.icon-action-btn.danger:hover {
  background: rgba(255, 69, 58, 0.15) !important;
  border-color: rgba(255, 69, 58, 0.4) !important;
  color: var(--danger, #ff453a) !important;
}

/* slide-fade transition */
.slide-fade-enter-active,
.slide-fade-leave-active {
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}
.slide-fade-enter-from,
.slide-fade-leave-to {
  transform: translateY(8px) scale(0.98);
  opacity: 0;
}
</style>
