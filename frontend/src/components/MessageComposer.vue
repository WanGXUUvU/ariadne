<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';

const props = defineProps<{
  disabled: boolean;
  messageCount?: number;
}>();

const emit = defineEmits<{
  (e: 'send', text: string): void;
}>();

const text = ref('');
const textareaRef = ref<HTMLTextAreaElement | null>(null);

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
      <span>INPUT_STREAM</span>
      <div style="display: flex; gap: 16px;">
        <span v-if="messageCount !== undefined" :style="{ color: messageCount > 10 ? '#FF453A' : 'var(--text-muted)' }">
          {{ messageCount }} / 12 TO AUTO-COMPACT
        </span>
        <span>[ENTER] TO SEND</span>
      </div>
    </div>
    <div class="composer-body">
      <textarea 
        ref="textareaRef"
        class="composer-input"
        v-model="text"
        @input="adjustHeight"
        @keydown="handleKeyDown"
        placeholder="Type a command or message..."
        :disabled="disabled"
        rows="1"
      ></textarea>
      <button 
        class="tech-btn primary"
        @click="handleSend"
        :disabled="disabled || !text.trim()"
      >
        <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.composer-container {
  border-top: 1px solid var(--border-dim);
  background: var(--bg-app);
  padding: 16px 24px;
}

.composer-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  color: var(--text-muted);
}

.composer-body {
  display: flex;
  gap: 12px;
  align-items: flex-end;
}

.composer-input {
  flex: 1;
  background: transparent;
  border: 1px solid var(--border-dim);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 14px;
  line-height: 1.5;
  padding: 10px 12px;
  resize: none;
  min-height: 40px;
  max-height: 160px;
  transition: var(--transition-fast);
}

.composer-input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 1px var(--accent-subtle, rgba(255,255,255,0.06));
}

.composer-input:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.composer-input::placeholder {
  color: var(--text-muted);
}

.tech-btn.primary {
  width: 40px;
  height: 40px;
  padding: 0;
}
</style>
