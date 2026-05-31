<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue';
import type { AgentMessage, TraceRunSummary, StreamingItem, ApprovalInfo } from '../types';
import AssistantMessage from './chat/AssistantMessage.vue';
import { formatContent } from '../utils/formatContent';

const props = defineProps<{
  messages: AgentMessage[];
  isLoading: boolean;
  isCompacting?: boolean;
  traceRuns?: TraceRunSummary[];
  isStreaming?: boolean;
  streamingTimeline?: StreamingItem[];
  lastCompletedRun?: TraceRunSummary | null;
  
  // 审批相关
  isAwaitingApproval?: boolean;
  pendingApprovalInfo?: ApprovalInfo | null;
  isProcessingApproval?: boolean;
}>();

const emit = defineEmits<{
  (e: 'approve'): void;
  (e: 'reject'): void;
  (e: 'approve-all'): void;
}>();

const listRef = ref<HTMLElement | null>(null);

const visibleMessages = computed(() =>
  props.messages.filter((message) => 
    message.role === 'user' || 
    (message.role === 'assistant' && !!message.content)
  )
);

// 流式滚动定位
watch([() => visibleMessages.value.length, () => props.isLoading, () => props.isCompacting, () => props.streamingTimeline?.length], async () => {
  await nextTick();
  if (listRef.value) {
    listRef.value.scrollTo({
      top: listRef.value.scrollHeight,
      behavior: 'smooth'
    });
  }
}, { deep: true });

// 💡 采用事件代理拦截来自子元素代码块中 Copy 按钮的点击事件，安全、快速且彻底免除 inline JS 漏洞
const handleCodeBlockClick = (e: MouseEvent) => {
  const target = e.target as HTMLElement;
  const btn = target.closest('.copy-code-btn') as HTMLButtonElement | null;
  if (!btn) return;

  const codeBlock = btn.closest('.code-block');
  const codeEl = codeBlock?.querySelector('pre code');
  if (!codeEl) return;

  const rawCode = codeEl.textContent || '';

  navigator.clipboard.writeText(rawCode)
    .then(() => {
      btn.classList.add('copied');
      const textSpan = btn.querySelector('.copy-text');
      if (textSpan) textSpan.textContent = 'Copied';

      setTimeout(() => {
        btn.classList.remove('copied');
        if (textSpan) textSpan.textContent = 'Copy';
      }, 2000);
    })
    .catch(err => {
      console.error('📋 复制代码块失败:', err);
    });
};
</script>

<template>
  <div v-if="visibleMessages.length === 0 && !isCompacting" class="message-list empty"></div>
  <div v-else class="message-list" ref="listRef">
    <template v-for="(m, idx) in visibleMessages" :key="idx">
      <!-- 💡 A-2 动态分割线注入：上一条为非活跃，当前为活跃时 -->
      <div 
        v-if="idx > 0 && !visibleMessages[idx - 1].isActive && m.isActive" 
        class="memory-boundary-divider-row"
      >
        <div class="message-row-inner" style="width: 100%;">
          <!-- 如果 m 带有 summary_text，说明是 Compaction，渲染记忆折叠线 -->
          <div v-if="m.summary_text" class="compact-alert premium-compaction" style="width: 100%;" :title="m.summary_text">
            <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none"><path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"></path><path d="M12 12v9"></path><path d="M8 17l4 4 4-4"></path></svg>
            <span class="pulse-dot"></span>
            <span>AI 记忆分割线 · 线上消息已折叠压缩 (Context Compacted)</span>
          </div>
          <!-- 如果没有 summary_text，说明是重置会话导致的划分，渲染重置分割线 -->
          <div v-else class="reset-alert" style="width: 100%;">
            <div class="reset-line"></div>
            <div class="reset-text">
              <span>上下文已重设 (Context Reset)</span>
              <span class="sub">以上内容已不再被模型记忆感知</span>
            </div>
            <div class="reset-line"></div>
          </div>
        </div>
      </div>

      <div :class="['message-row', `role-${m.role}`, m.isActive ? 'active-context' : 'compacted-context']">
        <div class="message-row-inner">
          <div class="message-avatar">
            <svg v-if="m.role === 'user'" viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
            <svg v-else class="ai-avatar glow" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l3 6.5 7 1-5 4.5 1.5 7-6.5-3.5-6.5 3.5 1.5-7-5-4.5 7-1z"></path></svg>
          </div>
          
          <div class="message-content">
            <div class="message-meta mono-label">{{ m.role === 'user' ? 'USER' : 'AGENT' }}</div>
            
            <!-- AI 回复代理层 -->
            <template v-if="m.role === 'assistant'">
              <AssistantMessage
                :message="m"
                :msgIndex="idx"
                :isLast="idx === visibleMessages.length - 1"
                :traceRuns="traceRuns"
                :lastCompletedRun="lastCompletedRun"
                :isAwaitingApproval="isAwaitingApproval"
                :pendingApprovalInfo="pendingApprovalInfo"
                :isProcessingApproval="isProcessingApproval"
                @approve="emit('approve')"
                @reject="emit('reject')"
                @approve-all="emit('approve-all')"
              />
            </template>

            <!-- 用户消息渲染 -->
            <template v-else>
              <div v-if="m.skill_name" class="msg-skill-badge">
                <span class="msg-skill-icon">📚</span>
                <span class="msg-skill-name">{{ m.skill_name }}</span>
              </div>
              <div class="message-text" v-html="formatContent(m.content)" @click="handleCodeBlockClick"></div>
            </template>
          </div>
        </div>
      </div>
    </template>
    
    <!-- 记忆折叠中的 Loading 状态 -->
    <div v-if="isCompacting" class="message-row role-assistant pending">
      <div class="message-row-inner">
        <div class="message-avatar">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="var(--text-muted)" stroke-width="2" class="spin"><path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"></path><path d="M12 12v9"></path><path d="M8 17l4 4 4-4"></path></svg>
        </div>
        <div class="message-content">
          <div class="message-meta mono-label" style="color: var(--text-muted)">SYSTEM <span class="blink" style="color: var(--text-muted)">COMPACTING...</span></div>
          <div class="message-text" style="color: var(--text-muted); font-style: italic;">正在生成上下文摘要并折叠历史记录 (Compressing context)...</div>
        </div>
      </div>
    </div>
    
    <!-- SSE 流输出实时代理卡片 -->
    <div v-if="isStreaming" class="message-row role-assistant pending">
      <div class="message-row-inner">
        <div class="message-avatar">
          <div class="ai-avatar-wrapper streaming-active">
            <div class="pulse-ring ring-1"></div>
            <div class="pulse-ring ring-2"></div>
            <div class="pulse-ring ring-3"></div>
            <svg class="ai-avatar spin glow" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l3 6.5 7 1-5 4.5 1.5 7-6.5-3.5-6.5 3.5 1.5-7-5-4.5 7-1z"></path></svg>
          </div>
        </div>
        
        <div class="message-content">
          <div class="message-meta mono-label">AGENT <span class="blink">STREAMING...</span></div>

          <template v-if="streamingTimeline && streamingTimeline.length > 0">
            <!-- 代理实时消息渲染 -->
            <AssistantMessage
              :message="{ role: 'assistant', content: '', timeline: streamingTimeline }"
              :msgIndex="9999"
              :isLast="true"
              :traceRuns="traceRuns"
              :lastCompletedRun="lastCompletedRun"
              :isAwaitingApproval="isAwaitingApproval"
              :pendingApprovalInfo="pendingApprovalInfo"
              :isProcessingApproval="isProcessingApproval"
              @approve="emit('approve')"
              @reject="emit('reject')"
              @approve-all="emit('approve-all')"
            />
          </template>
          <div v-else class="message-text loader-block"></div>
        </div>
      </div>
    </div>

    <!-- 加载指示器 -->
    <div v-if="isLoading && !isStreaming && !isCompacting" class="message-row role-assistant pending">
      <div class="message-row-inner">
        <div class="message-avatar">
          <svg class="ai-avatar spin glow" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l3 6.5 7 1-5 4.5 1.5 7-6.5-3.5-6.5 3.5 1.5-7-5-4.5 7-1z"></path></svg>
        </div>
        <div class="message-content">
          <div class="message-meta mono-label">AGENT <span class="blink">EXECUTING...</span></div>
          <div class="message-text loader-block"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 24px 0;
}

.message-row {
  display: flex;
  gap: 16px;
  padding: 16px 24px;
  border-bottom: 1px solid var(--border-dim);
  animation: messageSlideUp 0.45s cubic-bezier(0.34, 1.56, 0.64, 1) both;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.message-row.compacted-context {
  opacity: 0.55;
  filter: grayscale(35%) contrast(90%);
}

.message-row.compacted-context:hover {
  opacity: 0.9;
  filter: grayscale(0%) contrast(100%);
}

.memory-boundary-divider-row {
  display: flex;
  justify-content: center;
  padding: 28px 24px;
  animation: messageSlideUp 0.5s ease both;
}

.memory-boundary-divider-row .message-row-inner {
  display: flex;
  align-items: center;
  gap: 16px;
}

.compact-alert.premium-compaction {
  background: rgba(var(--accent-rgb, 99, 102, 241), 0.08);
  border: 1px solid rgba(var(--accent-rgb, 99, 102, 241), 0.35);
  box-shadow: 0 0 16px rgba(var(--accent-rgb, 99, 102, 241), 0.15);
}

.pulse-dot {
  width: 6px;
  height: 6px;
  background-color: var(--accent, #6366f1);
  border-radius: 50%;
  box-shadow: 0 0 8px var(--accent, #6366f1);
  animation: pulse 2s infinite;
  margin-right: 4px;
}

@keyframes pulse {
  0% {
    transform: scale(0.9);
    box-shadow: 0 0 0 0 rgba(99, 102, 241, 0.7);
  }
  70% {
    transform: scale(1);
    box-shadow: 0 0 0 6px rgba(99, 102, 241, 0);
  }
  100% {
    transform: scale(0.9);
    box-shadow: 0 0 0 0 rgba(99, 102, 241, 0);
  }
}

.message-row:last-child {
  border-bottom: none;
}

.role-user {
  background: transparent;
}

.msg-skill-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  background: var(--accent-subtle);
  border: 1px solid var(--accent-glow);
  border-radius: 6px;
  padding: 3px 8px 3px 6px;
  margin-bottom: 6px;
  font-size: 11px;
  color: var(--accent);
  font-family: var(--font-mono, monospace);
  font-weight: 600;
}

.msg-skill-icon {
  font-size: 12px;
}

.msg-skill-name {
  letter-spacing: 0.02em;
}

.role-assistant {
  background: transparent;
}

.ai-avatar {
  filter: drop-shadow(0 0 6px var(--accent-glow));
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.ai-avatar:hover {
  transform: scale(1.1);
  filter: drop-shadow(0 0 10px var(--accent));
}

@keyframes dropInElastic {
  0% { opacity: 0; transform: translateY(-10px) scale(0.95); }
  60% { opacity: 1; transform: translateY(2px) scale(1.02); }
  100% { opacity: 1; transform: translateY(0) scale(1); }
}

.stagger-anim {
  opacity: 0;
  animation: dropInElastic 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
}

/* ── AI Avatar 流光脉冲环 ── */
.ai-avatar-wrapper {
  position: relative;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.ai-avatar-wrapper.streaming-active .pulse-ring {
  position: absolute;
  border-radius: 50%;
  background: transparent;
  border: 1px solid rgba(var(--accent-rgb, 99, 102, 241), 0.3);
  animation: pulseOut 2s cubic-bezier(0.21, 0.6, 0.35, 1) infinite;
  z-index: 1;
}

.ai-avatar-wrapper.streaming-active .ring-1 {
  width: 28px;
  height: 28px;
  animation-delay: 0s;
}

.ai-avatar-wrapper.streaming-active .ring-2 {
  width: 32px;
  height: 32px;
  animation-delay: 0.6s;
}

.ai-avatar-wrapper.streaming-active .ring-3 {
  width: 36px;
  height: 36px;
  animation-delay: 1.2s;
}

@keyframes pulseOut {
  0% {
    transform: scale(0.85);
    opacity: 0.6;
    border-color: rgba(var(--accent-rgb, 99, 102, 241), 0.4);
  }
  100% {
    transform: scale(1.4);
    opacity: 0;
    border-color: rgba(var(--accent-rgb, 99, 102, 241), 0);
  }
}
</style>
