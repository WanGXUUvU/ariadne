import re

with open('src/components/MessageComposer.vue', 'r') as f:
    content = f.read()

template = """<template>
  <div class="composer-container">
    <div class="composer-header mono-label">
      <span>INPUT_STREAM</span>
      <div style="display: flex; gap: 16px;">
        <span v-if="messageCount !== undefined" :style="{ color: messageCount > 10 ? 'var(--danger)' : 'var(--text-muted)' }">
          {{ messageCount }} / 12 TURNS
        </span>
        <span>⏎ SEND / ⇧⏎ NEWLINE</span>
      </div>
    </div>
    <div class="composer-wrapper" :class="{ 'is-disabled': disabled, 'is-focused': isFocused }">
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
        @click="handleSend"
        :disabled="disabled || !text.trim()"
      >
        <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
          <line x1="12" y1="19" x2="12" y2="5"></line>
          <polyline points="5 12 12 5 19 12"></polyline>
        </svg>
      </button>
    </div>
  </div>
</template>"""

content = re.sub(r'<template>.*?</template>', template, content, flags=re.DOTALL)

script_insert = """const isFocused = ref(false);"""
content = content.replace("const textareaRef = ref<HTMLTextAreaElement | null>(null);", "const textareaRef = ref<HTMLTextAreaElement | null>(null);\n" + script_insert)

style = """<style scoped>
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
}

.composer-wrapper.is-focused {
  border-color: var(--accent-subtle);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4), 0 0 0 1px var(--accent-subtle);
}

.composer-wrapper.is-disabled {
  opacity: 0.6;
  pointer-events: none;
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
</style>"""

content = re.sub(r'<style scoped>.*?</style>', style, content, flags=re.DOTALL)

with open('src/components/MessageComposer.vue', 'w') as f:
    f.write(content)

