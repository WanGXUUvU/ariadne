import re

with open('frontend/src/components/MessageList.vue', 'r') as f:
    content = f.read()

html_marker = """      <template v-if="m.role === 'system'">
        <!-- 只显示提示条，不渲染 LLM 原始 summary 文字，避免模型输出噪音暴露给用户 -->
        <div v-if="m.content?.includes('[COMPACT_SUMMARY]')" class="compact-alert">
          <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none"><path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"></path><path d="M12 12v9"></path><path d="M8 17l4 4 4-4"></path></svg>
          上下文已压缩 — 部分历史已折叠为摘要 (Context Compacted)
        </div>
        <div v-else-if="m.content?.includes('[RESET_MARKER]')" class="reset-alert">
          <div class="reset-line"></div>
          <div class="reset-text">
            <span>上下文已重设 (Context Reset)</span>
            <span class="sub">以上内容已不再被模型感知</span>
          </div>
          <div class="reset-line"></div>
        </div>
      </template>"""

content = content.replace("""      <template v-if="m.role === 'system'">
        <!-- 只显示提示条，不渲染 LLM 原始 summary 文字，避免模型输出噪音暴露给用户 -->
        <div class="compact-alert">
          <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none"><path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"></path><path d="M12 12v9"></path><path d="M8 17l4 4 4-4"></path></svg>
          上下文已压缩 — 部分历史已折叠为摘要 (Context Compacted)
        </div>
      </template>""", html_marker)

vis_msgs_old = """const visibleMessages = computed(() =>
  props.messages.filter((message) => 
    message.role === 'user' || 
    (message.role === 'assistant' && !!message.content) ||
    (message.role === 'system' && message.content?.includes('[COMPACT_SUMMARY]'))
  )
);"""

vis_msgs_new = """const visibleMessages = computed(() =>
  props.messages.filter((message) => 
    message.role === 'user' || 
    (message.role === 'assistant' && !!message.content) ||
    (message.role === 'system' && (message.content?.includes('[COMPACT_SUMMARY]') || message.content?.includes('[RESET_MARKER]')))
  )
);"""

content = content.replace(vis_msgs_old, vis_msgs_new)

# Add CSS
css_add = """
.reset-alert {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
  margin: 16px 0;
  padding: 0 20px;
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
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-muted);
  text-align: center;
}

.reset-text .sub {
  font-size: 10px;
  opacity: 0.6;
}

.spin {"""

content = content.replace(".spin {", css_add)

with open('frontend/src/components/MessageList.vue', 'w') as f:
    f.write(content)

