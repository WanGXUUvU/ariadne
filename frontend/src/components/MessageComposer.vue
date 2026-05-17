<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';

const props = defineProps<{
  disabled: boolean;
  messageCount?: number;
  isStreaming?: boolean;
}>();

const emit = defineEmits<{
  (e: 'send', text: string): void;
  (e: 'stop'): void;
}>();

const text = ref('');
const textareaRef = ref<HTMLTextAreaElement | null>(null);
const isFocused = ref(false);

const adjustHeight = () => {
  if (!textareaRef.value) return;
  textareaRef.value.style.height = 'auto';
  textareaRef.value.style.height = `${Math.min(textareaRef.value.scrollHeight, 160)}px`;
};

watch(text, () => {
  nextTick(adjustHeight);
});

const handleSend = () => {
  if (!text.value.trim() || props.disabled) return;
  emit('send', text.value.trim());
  text.value = '';
  nextTick(adjustHeight);
};

const handleKeyDown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    // If user is currently composing text using an IME (like Chinese/Japanese pinyin),
    // do not trigger the send action.
    if (e.isComposing || e.keyCode === 229) {
      return;
    }
    e.preventDefault();
    handleSend();
  }
};
</script>

<template>
  <div class="composer-container">
    <div class="composer-header mono-label">
      <span class="composer-hint">Ask anything</span>
      <div style="display: flex; gap: 16px; align-items: center;">
        <span v-if="messageCount !== undefined && messageCount > 0" class="turn-counter" :class="{ 'turn-warn': messageCount >= 10 }">
          {{ messageCount }} msg
        </span>
        <span class="key-hint"><kbd>↩</kbd> send &nbsp;<kbd>⇧↩</kbd> newline</span>
      </div>
    </div>
    <div class="composer-wrapper" :class="{ 'is-disabled': disabled, 'is-focused': isFocused, 'is-streaming': isStreaming }">
      <textarea 
        ref="textareaRef"
        class="composer-input"
        v-model="text"
        @input="adjustHeight"
        @keydown="handleKeyDown"
        @focus="isFocused = true"
        @blur="isFocused = false"
        placeholder="Ask anything or request a tool..."
        :disabled="disabled"
        rows="1"
      ></textarea>
      <button 
        class="send-btn"
        :class="{ 'is-stop': isStreaming }"
        @click="isStreaming ? emit('stop') : handleSend()"
        :disabled="!isStreaming && (disabled || !text.trim())"
        :title="isStreaming ? 'Stop generation' : 'Send'"
      >
        <!-- Stop 正方形图标 -->
        <svg v-if="isStreaming" viewBox="0 0 24 24" width="12" height="12" fill="currentColor">
          <rect x="4" y="4" width="16" height="16" rx="3"/>
        </svg>
        <!-- 发送箭头图标 -->
        <svg v-else viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
          <line x1="12" y1="19" x2="12" y2="5"></line>
          <polyline points="5 12 12 5 19 12"></polyline>
        </svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.composer-container {
  padding: 16px 24px 24px;
  background: linear-gradient(to top, var(--bg-app) 70%, transparent);
  position: relative;
  z-index: 10;
}

.composer-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  color: var(--text-muted);
  font-size: 10px;
}

.composer-wrapper {
  display: flex;
  align-items: flex-end;
  background: var(--bg-elevated);
  border: 1px solid var(--border-dim);
  border-radius: 16px;
  padding: 8px 12px;
  transition: all 0.3s cubic-bezier(0.2, 0.9, 0.3, 1);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.2);
  position: relative;
}

/* 氛围光旋转层（在输入框背后转圈） */
@property --ambient-angle {
  syntax: '<angle>';
  inherits: false;
  initial-value: 0deg;
}

@keyframes ambient-rotate {
  to { --ambient-angle: 360deg; }
}

.composer-wrapper.is-streaming::before {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: 18px;
  background: conic-gradient(
    from var(--ambient-angle),
    transparent 55%,
    #7c6af7 70%,
    #a78bfa 80%,
    #7fd4f7 88%,
    #f7a78b 94%,
    transparent
  );
  z-index: -1;
  animation: ambient-rotate 2.5s linear infinite;
}

.composer-wrapper.is-focused {
  border-color: var(--accent-subtle);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4), 0 0 0 1px var(--accent-subtle);
}

.composer-hint {
  color: var(--text-muted);
  font-size: 10px;
  letter-spacing: 0.05em;
}
.turn-counter {
  color: var(--text-muted);
  font-size: 10px;
  font-family: var(--font-mono, monospace);
}
.turn-warn {
  color: var(--accent);
}
.key-hint {
  font-size: 10px;
  color: var(--text-muted);
  opacity: 0.7;
}
.key-hint kbd {
  font-family: var(--font-mono, monospace);
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 3px;
  padding: 1px 4px;
  font-size: 9px;
}

.composer-input {
  flex: 1;
  background: transparent;
  border: none;
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.5;
  padding: 4px 0;
  resize: none;
  min-height: 24px;
  max-height: 200px;
  margin-right: 12px;
}

.composer-input:focus {
  outline: none;
}

.composer-input::placeholder {
  color: var(--text-muted);
}

.send-btn {
  background: var(--accent);
  color: var(--bg-app);
  border: none;
  border-radius: 10px;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: transform 0.2s ease, opacity 0.2s ease;
  flex-shrink: 0;
  margin-bottom: 2px;
}

.send-btn:hover:not(:disabled) {
  transform: scale(1.05);
}

.send-btn:active:not(:disabled) {
  transform: scale(0.95);
}

.send-btn:disabled {
  background: var(--bg-hover);
  color: var(--text-muted);
  cursor: not-allowed;
}

/* streaming 时变成红色方形 Stop 按钮 */
.send-btn.is-stop {
  background: rgba(220, 70, 70, 0.9);
  color: #fff;
  cursor: pointer;
  opacity: 1;
}
.send-btn.is-stop:hover {
  background: rgba(220, 70, 70, 1);
  transform: scale(1.05);
}
</style>
