<script setup lang="ts">
import { computed, ref, watch, nextTick, onBeforeUnmount } from 'vue';
import type { AgentMessage, TraceRunSummary, StreamingItem, ApprovalInfo, StreamUsageData } from '../types';
import AssistantMessage from './chat/AssistantMessage.vue';
import { formatContent } from '../utils/formatContent';
import { RESET_MARKER_CONTENT } from '../composables/workspace/helpers';

const props = defineProps<{
  messages: AgentMessage[];
  isLoading: boolean;
  isCompacting?: boolean;
  traceRuns?: TraceRunSummary[];
  isStreaming?: boolean;
  streamingTimeline?: StreamingItem[];
  streamingPrefixTimeline?: StreamingItem[]; // 审批批准后的前缀 timeline（initialTimeline），与 streamingTimeline 合并渲染
  streamingLatestUsage?: StreamUsageData | null;
  lastCompletedRun?: TraceRunSummary | null;
  error?: string | null;
  
  // 审批相关
  isAwaitingApproval?: boolean;
  pendingApprovalInfo?: ApprovalInfo | null;
  pendingApprovalInfos?: ApprovalInfo[];
  isProcessingApproval?: boolean;
}>();

const emit = defineEmits<{
  (e: 'approve', approvalId?: string): void;
  (e: 'reject', approvalId?: string): void;
  (e: 'approve-all'): void;
  (e: 'retry'): void;
  (e: 'edit-submit', index: number, content: string): void;
}>();

const listRef = ref<HTMLElement | null>(null);

// 用户向上滚动检测 - 只有用户在底部附近时才自动滚动
const isUserScrolledUp = ref(false);

const handleScroll = () => {
  if (!listRef.value) return;
  const { scrollTop, scrollHeight, clientHeight } = listRef.value;
  // 如果用户距离底部超过 120px，认为用户在手动浏览历史
  isUserScrolledUp.value = scrollHeight - scrollTop - clientHeight > 120;
};

// 监听 listRef 变化（因为是条件渲染），动态绑定/解绑滚动事件
watch(listRef, (el, oldEl, onCleanup) => {
  if (el) {
    el.addEventListener('scroll', handleScroll, { passive: true });
    onCleanup(() => el.removeEventListener('scroll', handleScroll));
  }
});

const editingIndex = ref<number | null>(null);
const editingContent = ref<string>('');

const startEdit = (content: string, index: number) => {
  editingIndex.value = index;
  editingContent.value = content;
};

const cancelEdit = () => {
  editingIndex.value = null;
  editingContent.value = '';
};

const submitEdit = (index: number) => {
  if (!editingContent.value.trim()) return;
  emit('edit-submit', index, editingContent.value);
  editingIndex.value = null;
  editingContent.value = '';
};

const handleEditSubmit = (m: AgentMessage) => {
  const originalIndex = props.messages.indexOf(m);
  if (originalIndex !== -1) {
    submitEdit(originalIndex);
  }
};

const visibleMessages = computed(() => {
  const msgs = props.messages.filter((message) =>
    message.role === 'user' ||
    (message.role === 'assistant' && (!!message.content || (message.timeline && message.timeline.length > 0)))
  );

  // 将流式输出块并入 visibleMessages，使其与最终消息共享同一个 DOM 元素，
  // 避免 end 时 v-if 移除流式块 + v-for 新增消息行导致的闪烁
  if (props.isStreaming) {
    const timeline = [...(props.streamingPrefixTimeline ?? []), ...(props.streamingTimeline ?? [])];
    msgs.push({
      role: 'assistant' as const,
      content: '',
      timeline,
      _streaming: true,
    } as AgentMessage & { _streaming?: boolean });
  }

  return msgs;
});

// ── 自动滚动 ──────────────────────────────────────────────────────────────
// 非流式：只在消息数/loading 变化时滚动一次（轻量 watcher）
watch(
  [() => visibleMessages.value.length, () => props.isLoading, () => props.isCompacting],
  async () => {
    await nextTick();
    if (listRef.value && !isUserScrolledUp.value) {
      listRef.value.scrollTop = listRef.value.scrollHeight;
    }
  }
);

// 流式：用 requestAnimationFrame 循环跟随底部，避免 deep watch 的 O(n) 遍历
let rafId: number | null = null;

const startScrollLoop = () => {
  if (rafId !== null) return;
  const loop = () => {
    if (listRef.value && !isUserScrolledUp.value) {
      listRef.value.scrollTop = listRef.value.scrollHeight;
    }
    if (props.isStreaming) {
      rafId = requestAnimationFrame(loop);
    } else {
      rafId = null;
    }
  };
  rafId = requestAnimationFrame(loop);
};

const stopScrollLoop = () => {
  if (rafId !== null) {
    cancelAnimationFrame(rafId);
    rafId = null;
  }
};

watch(() => props.isStreaming, (streaming) => {
  if (streaming) {
    startScrollLoop();
  } else {
    stopScrollLoop();
    // 流式结束后再滚一次确保对齐底部
    nextTick(() => {
      if (listRef.value && !isUserScrolledUp.value) {
        listRef.value.scrollTop = listRef.value.scrollHeight;
      }
    });
  }
});

onBeforeUnmount(() => stopScrollLoop());

// 当新会话加载时（消息列表清空后重建），重置滚动锁定状态
watch(() => visibleMessages.value.length, (newLen, oldLen) => {
  // 消息数归零说明切换了会话，重置滚动状态
  if (oldLen > 0 && newLen === 0) {
    isUserScrolledUp.value = false;
  }
});


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

const copiedIndex = ref<number | null>(null);
const runStartedAt = ref<number | null>(null);
const heartbeatTick = ref(0);
let heartbeatTimer: number | null = null;

const activityWords = ['Thinking', 'Hashing', 'Reading', 'Checking', 'Composing', 'Planning'];
const activityTips = [
  '工具结果会先进入上下文，模型再基于结果继续生成。',
  '如果模型需要更多证据，它会继续请求工具而不是直接猜测。',
  '长回答通常会先整理结构，再逐段输出。',
  '运行中显示的是估算 token，模型返回 usage 后会替换成准确值。',
  '工具调用本身不产生模型 usage，只有模型调用结束时才会返回。',
];

const startHeartbeat = () => {
  if (heartbeatTimer !== null) return;
  heartbeatTimer = window.setInterval(() => {
    heartbeatTick.value += 1;
  }, 900);
};

const stopHeartbeat = () => {
  if (heartbeatTimer !== null) {
    window.clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }
};

watch(() => props.isStreaming, (streaming) => {
  if (streaming) {
    runStartedAt.value = Date.now();
    heartbeatTick.value = 0;
    startHeartbeat();
  } else {
    runStartedAt.value = null;
    stopHeartbeat();
  }
}, { immediate: true });

onBeforeUnmount(() => {
  stopHeartbeat();
});

const activeWord = computed(() => activityWords[heartbeatTick.value % activityWords.length]);
const activeTip = computed(() => activityTips[Math.floor(heartbeatTick.value / 2) % activityTips.length]);
const elapsedSeconds = computed(() => {
  if (!runStartedAt.value) return 0;
  heartbeatTick.value;
  return Math.max(0, Math.floor((Date.now() - runStartedAt.value) / 1000));
});

const streamingTextSize = computed(() => {
  const items = [...(props.streamingPrefixTimeline ?? []), ...(props.streamingTimeline ?? [])];
  return items.reduce((sum, item) => {
    if (item.kind === 'text' || item.kind === 'thinking') return sum + item.content.length;
    return sum;
  }, 0);
});

const displayTokens = computed(() => {
  const real = props.streamingLatestUsage?.usage?.total_tokens
    ?? props.streamingLatestUsage?.usage?.input_tokens
    ?? props.streamingLatestUsage?.usage?.output_tokens
    ?? null;
  if (typeof real === 'number') {
    return { value: real, estimated: false };
  }
  const estimate = Math.max(8, Math.ceil(streamingTextSize.value / 3) + heartbeatTick.value * 3);
  return { value: estimate, estimated: true };
});

const handleCopyMessage = (content: string, index: number) => {
  navigator.clipboard.writeText(content).then(() => {
    copiedIndex.value = index;
    setTimeout(() => {
      if (copiedIndex.value === index) {
        copiedIndex.value = null;
      }
    }, 2000);
  }).catch(err => {
    console.error('📋 复制对话内容失败:', err);
  });
};

const scrollToBottom = () => {
  if (!listRef.value) return;
  listRef.value.scrollTo({ top: listRef.value.scrollHeight, behavior: 'smooth' });
  isUserScrolledUp.value = false;
};

const resetMarker = RESET_MARKER_CONTENT;
</script>

<template>
  <div v-if="visibleMessages.length === 0 && !isCompacting" class="message-list empty"></div>
  <div v-else class="message-list" ref="listRef">
    <!-- 滚动到底部浮动按钮 -->
    <Transition name="scroll-btn">
      <button
        v-if="isUserScrolledUp"
        class="scroll-to-bottom-btn"
        @click="scrollToBottom"
        :title="isStreaming ? 'AI 正在输出——下滑查看' : '滚动到最新消息'"
      >
        <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2.5" fill="none">
          <line x1="12" y1="5" x2="12" y2="19"></line>
          <polyline points="19 12 12 19 5 12"></polyline>
        </svg>
        <span v-if="isStreaming" class="scroll-btn-label streaming-pulse">AI 输出中</span>
        <span v-else class="scroll-btn-label">最新</span>
      </button>
    </Transition>
    <template v-for="(m, idx) in visibleMessages" :key="(m as any)._streaming ? '__streaming__' : (m.run_id ? m.run_id + '-' + m.role : m.role + '-' + idx)">
      <!-- 💡 如果是系统重设标记，渲染重置分割线 -->
      <template v-if="m.role === 'system' && m.content === resetMarker">
        <div class="memory-boundary-divider-row">
          <div class="message-row-inner" style="width: 100%;">
            <div class="reset-alert" style="width: 100%;">
              <div class="reset-line"></div>
              <div class="reset-text">
                <span>上下文已重设 (Context Reset)</span>
                <span class="sub">以上内容已不再被模型记忆感知</span>
              </div>
              <div class="reset-line"></div>
            </div>
          </div>
        </div>
      </template>

      <!-- 否则如果是正常的用户/助理消息，正常渲染 -->
      <template v-else-if="m.role !== 'system'">
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

        <div :class="['message-row', `role-${m.role}`, m.isActive ? 'active-context' : 'compacted-context', (m as any)._streaming ? 'pending' : '']">
          <div class="message-row-inner">
            <div class="message-avatar">
              <!-- 流式输出：脉冲光环头像 -->
              <template v-if="(m as any)._streaming">
                <div class="ai-avatar-wrapper streaming-active">
                  <div class="pulse-ring ring-1"></div>
                  <div class="pulse-ring ring-2"></div>
                  <div class="pulse-ring ring-3"></div>
                  <svg class="ai-avatar spin glow" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l3 6.5 7 1-5 4.5 1.5 7-6.5-3.5-6.5 3.5 1.5-7-5-4.5 7-1z"></path></svg>
                </div>
              </template>
              <!-- 普通消息头像 -->
              <template v-else>
                <svg v-if="m.role === 'user'" viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
                <svg v-else class="ai-avatar glow" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l3 6.5 7 1-5 4.5 1.5 7-6.5-3.5-6.5 3.5 1.5-7-5-4.5 7-1z"></path></svg>
              </template>
            </div>

            <div class="message-content">
              <div class="message-meta mono-label">
                {{ m.role === 'user' ? 'USER' : 'AGENT' }}
                <span v-if="(m as any)._streaming" class="blink">STREAMING...</span>
              </div>

              <!-- AI 回复代理层 -->
              <template v-if="m.role === 'assistant'">
                <!-- 流式空时间线：骨架屏 -->
                <div v-if="(m as any)._streaming && (!m.timeline || m.timeline.length === 0)" class="message-text loader-block"></div>
                <!-- 有内容：正常渲染 -->
                <AssistantMessage
                  v-else
                  :message="m"
                  :msgIndex="(m as any)._streaming ? 9999 : idx"
                  :isLast="idx === visibleMessages.length - 1"
                  :traceRuns="traceRuns"
                  :lastCompletedRun="lastCompletedRun"
                  :isAwaitingApproval="isAwaitingApproval"
                  :pendingApprovalInfo="pendingApprovalInfo"
                  :pendingApprovalInfos="pendingApprovalInfos"
                  :isProcessingApproval="isProcessingApproval"
                  @approve="emit('approve', $event)"
                  @reject="emit('reject', $event)"
                  @approve-all="emit('approve-all')"
                />
                <!-- 流式状态条：打字词 + 耗时 + token 估算 + 提示 -->
                <div v-if="(m as any)._streaming" class="agent-active-strip">
                  <div class="agent-active-main">
                    <span class="agent-active-word">{{ activeWord }}...</span>
                    <span class="agent-active-meta">
                      {{ elapsedSeconds }}s · {{ displayTokens.estimated ? '~' : '' }}{{ displayTokens.value }} tokens
                    </span>
                  </div>
                  <div class="agent-active-tip">└─ {{ activeTip }}</div>
                </div>
              </template>

              <!-- 用户消息渲染 -->
              <template v-else>
                <div v-if="m.skill_name" class="msg-skill-badge">
                  <span class="msg-skill-icon">📚</span>
                  <span class="msg-skill-name">{{ m.skill_name }}</span>
                </div>
                <!-- 编辑态 -->
                <div v-if="editingIndex === idx" class="message-edit-block">
                  <textarea
                    v-model="editingContent"
                    class="edit-textarea"
                    rows="3"
                    placeholder="编辑你的消息..."
                  ></textarea>
                  <div class="edit-actions">
                    <button class="edit-btn save" @click="handleEditSubmit(m)">保存并重发</button>
                    <button class="edit-btn cancel" @click="cancelEdit">取消</button>
                  </div>
                </div>
                <!-- 展示态 -->
                <div v-else class="message-text" v-html="formatContent(m.content)" @click="handleCodeBlockClick"></div>
              </template>

              <!-- Message Footer Action Row（流式消息不显示） -->
              <div v-if="!(m as any)._streaming" class="message-footer">
                <!-- 编辑按钮 -->
                <button
                  v-if="m.role === 'user' && editingIndex !== idx"
                  class="action-btn edit-action-btn"
                  title="编辑消息"
                  @click="startEdit(m.content || '', idx)"
                >
                  <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="1.8" fill="none">
                    <path d="M12 20h9"></path>
                    <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
                  </svg>
                </button>
                <button
                  class="action-btn copy-btn"
                  :class="{ copied: copiedIndex === idx }"
                  title="复制文本"
                  @click="handleCopyMessage(m.content || '', idx)"
                >
                  <svg v-if="copiedIndex !== idx" viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="1.8" fill="none">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                  </svg>
                  <svg v-else viewBox="0 0 24 24" width="14" height="14" stroke="var(--accent-emerald, #34c759)" stroke-width="2.2" fill="none">
                    <polyline points="20 6 9 17 4 12"></polyline>
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>
      </template>
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

    <!-- 错误指示器与重试卡片 -->
    <div v-if="error" class="message-row role-assistant error-row">
      <div class="message-row-inner">
        <div class="message-avatar">
          <div class="error-avatar-wrapper">
            <svg viewBox="0 0 24 24" width="16" height="16" stroke="var(--danger, #ff453a)" stroke-width="2" fill="none" class="error-svg">
              <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
              <line x1="12" y1="9" x2="12" y2="13"></line>
              <line x1="12" y1="17" x2="12.01" y2="17"></line>
            </svg>
          </div>
        </div>
        <div class="message-content">
          <div class="message-meta mono-label text-danger">RUN INTERRUPTED</div>
          <div class="error-retry-card">
            <div class="error-card-body">
              <div class="error-card-header">
                <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" class="warning-icon">
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="12" y1="8" x2="12" y2="12"></line>
                  <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
                <span class="error-title">Run interrupted</span>
              </div>
              <p class="error-text">{{ error }}</p>
              <div class="error-actions">
                <button class="retry-action-btn" @click="emit('retry')">
                  <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2.5" fill="none" class="retry-icon">
                    <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"></path>
                  </svg>
                  <span>Retry</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.message-content {
  position: relative;
  width: 100%;
}

.agent-active-strip {
  margin-top: 10px;
  padding-left: 2px;
  color: var(--text-muted);
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
  font-size: 12px;
  line-height: 1.55;
  animation: statusFadeIn 0.28s ease both;
}

.agent-active-main {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-height: 20px;
}

.agent-active-word {
  color: var(--accent, #a66a43);
  font-weight: 700;
}

.agent-active-meta {
  color: var(--text-muted);
  font-weight: 500;
}

.agent-active-tip {
  color: var(--text-secondary);
  opacity: 0.78;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

@keyframes statusFadeIn {
  from { opacity: 0; transform: translateY(3px); }
  to { opacity: 1; transform: translateY(0); }
}

.message-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  margin-top: 4px;
  width: 100%;
  opacity: 0;
  transition: opacity 0.25s ease;
}

.message-row:hover .message-footer {
  opacity: 1;
}

.action-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 4px;
  color: var(--text-muted) !important;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  outline: none;
}

.action-btn:hover {
  color: var(--text-primary) !important;
  background: var(--bg-hover) !important;
}

.action-btn.copied {
  color: var(--accent-emerald, #34c759) !important;
}

@media (max-width: 768px) {
  /* On mobile touch devices, show actions slightly transparent by default */
  .message-footer {
    opacity: 0.75;
  }
}

/* ── 滚动到底部浮动按钮 ── */
.scroll-to-bottom-btn {
  position: sticky;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px 6px 10px;
  background: rgba(var(--bg-panel-rgb, 10, 10, 10), 0.9);
  backdrop-filter: blur(16px);
  border: 1px solid var(--border-strong);
  border-radius: 99px;
  color: var(--text-secondary);
  font-size: 11px;
  font-family: var(--font-mono, monospace);
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
  white-space: nowrap;
  margin: 0 auto;
}

.scroll-to-bottom-btn:hover {
  color: var(--text-primary);
  border-color: var(--accent);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4), 0 0 12px var(--accent-glow);
  transform: translateX(-50%) translateY(-1px);
}

.scroll-btn-label {
  font-size: 10px;
  letter-spacing: 0.04em;
}

.scroll-btn-label.streaming-pulse {
  color: var(--accent);
  animation: pulse-text 1.5s ease-in-out infinite;
}

@keyframes pulse-text {
  0%, 100% { opacity: 0.7; }
  50% { opacity: 1; }
}

/* scroll-btn transition */
.scroll-btn-enter-active,
.scroll-btn-leave-active {
  transition: opacity 0.2s ease, transform 0.2s cubic-bezier(0.16, 1, 0.3, 1);
}
.scroll-btn-enter-from,
.scroll-btn-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(8px);
}

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

/* ── Premium Error Retry Card Styling ── */
.role-assistant.error-row {
  background: transparent;
}

.error-avatar-wrapper {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--warning-amber, #f59e0b) 8%, transparent);
  border: 1px solid color-mix(in srgb, var(--warning-amber, #f59e0b) 22%, var(--border-dim));
  border-radius: 50%;
  box-shadow: none;
}

.text-danger {
  color: var(--text-muted) !important;
}

.error-retry-card {
  margin-top: 8px;
  max-width: 520px;
  border-radius: 8px;
  background: var(--bg-hover);
  border: 1px solid var(--border-dim);
  box-shadow: none;
}

.error-card-body {
  padding: 14px 16px;
}

.error-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  color: var(--text-secondary);
}

.warning-icon {
  flex-shrink: 0;
}

.error-title {
  font-size: 13px;
  font-weight: 650;
  letter-spacing: 0;
}

.error-text {
  font-size: 12px;
  line-height: 1.55;
  color: var(--text-primary);
  margin: 0 0 12px 0;
  font-family: var(--font-mono, monospace);
  word-break: break-all;
}

.retry-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--border-dim);
  border-radius: 7px;
  background: var(--bg-panel);
  color: var(--text-primary);
  font-family: var(--font-mono, monospace);
  font-size: 11px;
  font-weight: 700;
  padding: 6px 11px;
  cursor: pointer;
  transition: background 0.16s ease, border-color 0.16s ease, transform 0.16s ease;
}

.retry-action-btn:hover {
  transform: translateY(-1px);
  border-color: var(--accent);
  background: color-mix(in srgb, var(--accent) 7%, var(--bg-panel));
}

.retry-action-btn:active {
  transform: translateY(0);
}

.btn-glow-layer {
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.25), transparent);
  transition: 0.5s;
}

.retry-action-btn:hover .btn-glow-layer {
  left: 100%;
  transition: 0.6s ease-in-out;
}
/* ── Premium Inline Textarea Editor ── */
.message-edit-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  margin-top: 8px;
}

.edit-textarea {
  width: 100%;
  min-height: 80px;
  padding: 12px;
  background: var(--bg-hover);
  border: 1px solid var(--border-dim);
  border-radius: 8px;
  color: var(--text-primary);
  font-family: inherit;
  font-size: 13px;
  line-height: 1.5;
  resize: vertical;
  outline: none;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.edit-textarea:focus {
  background: rgba(var(--accent-rgb, 99, 102, 241), 0.03);
  border-color: rgba(var(--accent-rgb, 99, 102, 241), 0.4);
  box-shadow: 0 0 12px rgba(var(--accent-rgb, 99, 102, 241), 0.1);
}

.edit-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.edit-btn {
  font-family: var(--font-mono, monospace);
  font-size: 11px;
  font-weight: 600;
  padding: 6px 14px;
  border-radius: 6px;
  cursor: pointer;
  border: none;
  transition: all 0.2s ease;
}

.edit-btn.save {
  background: linear-gradient(135deg, var(--accent, #6366f1), rgba(var(--accent-rgb, 99, 102, 241), 0.8));
  color: #ffffff;
  box-shadow: 0 4px 12px rgba(var(--accent-rgb, 99, 102, 241), 0.2);
}

.edit-btn.save:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(var(--accent-rgb, 99, 102, 241), 0.3);
}

.edit-btn.cancel {
  background: var(--bg-hover);
  border: 1px solid var(--border-dim);
  color: var(--text-secondary);
}

.edit-btn.cancel:hover {
  background: var(--bg-active);
  border-color: var(--border-strong);
  color: var(--text-primary);
}

.edit-action-btn {
  margin-right: 4px;
}

.reset-alert {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  width: 100%;
}

.reset-line {
  flex: 1;
  height: 1px;
  background: var(--border-dim);
}

.reset-text {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  text-align: center;
  user-select: none;
}

.reset-text span:first-child {
  font-family: var(--font-sans);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-secondary);
}

.reset-text span.sub {
  font-family: var(--font-sans);
  font-size: 10px;
  color: var(--text-muted);
}
</style>
