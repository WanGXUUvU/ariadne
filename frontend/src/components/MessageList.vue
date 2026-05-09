<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue';
import type { AgentMessage } from '../types';

const props = defineProps<{
  messages: AgentMessage[];
  isLoading: boolean;
  isCompacting?: boolean;
}>();

const listRef = ref<HTMLElement | null>(null);

const visibleMessages = computed(() =>
  props.messages.filter((message) => 
    message.role === 'user' || 
    (message.role === 'assistant' && !!message.content) ||
    (message.role === 'system' && (message.content?.includes('[COMPACT_SUMMARY]') || message.content?.includes('[RESET_MARKER]')))
  )
);

// Auto-scroll to bottom when messages change or loading state changes
watch([() => visibleMessages.value.length, () => props.isLoading, () => props.isCompacting], async () => {
  await nextTick();
  if (listRef.value) {
    listRef.value.scrollTop = listRef.value.scrollHeight;
  }
}, { deep: true });

// Basic markdown parser for code blocks, tables, and inline code
const formatContent = (text: string | null) => {
  if (!text) return '';
  // Hide the prefix from the user
  text = text.replace('[COMPACT_SUMMARY]\nThe following is a compressed summary of the middle part of the conversation. It is not a verbatim transcript. Preserve task goals, constraints, important tool results, and unfinished work.\n\n', '');
  
  // Escape HTML first
  let html = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  
  // Format code blocks: ```lang\ncode\n```
  html = html.replace(/```([\w-]*)\n([\s\S]*?)```/g, (_match, lang, code) => {
    const langLabel = lang ? `<div class="code-lang mono-label">${lang}</div>` : '';
    return `<div class="code-block">${langLabel}<pre><code>${code}</code></pre></div>`;
  });

  // Markdown tables: 连续的 | 开头行，中间有 |---| 分隔行
  html = html.replace(/((?:^\|.+\|$\n?){2,})/gm, (tableBlock) => {
    const rows = tableBlock.trim().split('\n').filter(r => r.trim());
    if (rows.length < 2) return tableBlock; // 至少要有表头 + 分隔行
    // 检查第二行是否是分隔行（|---|---|）
    const sepLine = rows[1];
    if (!/^\|[\s-:|]+\|$/.test(sepLine)) return tableBlock; // 不是合法表格

    const parseRow = (row: string) =>
      row.split('|').slice(1, -1).map(cell => cell.trim()); // 去掉首尾空 |，取中间各 cell

    const headerCells = parseRow(rows[0]);
    const bodyRows = rows.slice(2); // 跳过表头和分隔行

    let tableHtml = '<div class="md-table-wrapper"><table class="md-table">';
    tableHtml += '<thead><tr>' + headerCells.map(c => `<th>${c}</th>`).join('') + '</tr></thead>';
    tableHtml += '<tbody>';
    for (const row of bodyRows) {
      const cells = parseRow(row);
      tableHtml += '<tr>' + cells.map(c => `<td>${c}</td>`).join('') + '</tr>';
    }
    tableHtml += '</tbody></table></div>';
    return tableHtml;
  });
  
  // Format inline code: `code`
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');

  // Horizontal rule: --- 单独一行 → <hr>
  html = html.replace(/^---+$/gm, '<hr style="border:none;border-top:1px solid var(--border-dim);margin:12px 0;">');

  // Headings: ## text / ### text（放在 bold 之前，避免被 ** 处理干扰）
  html = html.replace(/^### (.+)$/gm, '<div style="font-size:13px;font-weight:600;color:var(--text-primary);margin:10px 0 4px;">$1</div>');
  html = html.replace(/^## (.+)$/gm, '<div style="font-size:14px;font-weight:600;color:var(--text-primary);margin:12px 0 4px;">$1</div>');
  html = html.replace(/^# (.+)$/gm, '<div style="font-size:15px;font-weight:700;color:var(--text-primary);margin:14px 0 4px;">$1</div>');

  // Bold: **text** → <strong>
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

  // Italic: *text* → <em>（单个 *，不碰 **）
  html = html.replace(/(?<!\*)\*(?!\*)([^*]+)(?<!\*)\*(?!\*)/g, '<em>$1</em>');

  // Unordered lists: 连续的 - 开头行 → <ul><li>
  html = html.replace(/((?:^- .+$\n?)+)/gm, (block) => {
    const items = block.trim().split('\n')
      .filter(l => l.trim().startsWith('- '))
      .map(l => `<li>${l.replace(/^- /, '')}</li>`);
    return `<ul class="md-list">${items.join('')}</ul>`;
  });

  // Ordered lists: 连续的 数字. 开头行 → <ol><li>
  html = html.replace(/((?:^\d+\. .+$\n?)+)/gm, (block) => {
    const items = block.trim().split('\n')
      .filter(l => /^\d+\. /.test(l.trim()))
      .map(l => `<li>${l.replace(/^\d+\. /, '')}</li>`);
    return `<ol class="md-list">${items.join('')}</ol>`;
  });

  return html;
};
</script>

<template>
  <div v-if="visibleMessages.length === 0 && !isCompacting" class="message-list empty">
    <!-- Empty state handled in ChatPanel -->
  </div>
  <div v-else class="message-list" ref="listRef">
    <div v-for="(m, idx) in visibleMessages" :key="idx" :class="['message-row', `role-${m.role}`]">
      <template v-if="m.role === 'system'">
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
      </template>
      <template v-else>
        <div class="message-avatar">
          <svg v-if="m.role === 'user'" viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
          <svg v-else viewBox="0 0 24 24" width="14" height="14" fill="var(--accent)" stroke="none"><polygon points="12 2 2 22 22 22"></polygon></svg>
        </div>
        <div class="message-content">
          <div class="message-meta mono-label">
            {{ m.role === 'user' ? 'USER' : 'AGENT' }}
          </div>
          <div class="message-text" v-html="formatContent(m.content)"></div>
        </div>
      </template>
    </div>
    
    <div v-if="isCompacting" class="message-row role-assistant pending">
      <div class="message-avatar">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="var(--text-muted)" stroke-width="2" class="spin"><path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"></path><path d="M12 12v9"></path><path d="M8 17l4 4 4-4"></path></svg>
      </div>
      <div class="message-content">
        <div class="message-meta mono-label" style="color: var(--text-muted)">SYSTEM <span class="blink" style="color: var(--text-muted)">COMPACTING...</span></div>
        <div class="message-text" style="color: var(--text-muted); font-style: italic;">正在生成上下文摘要并折叠历史记录 (Compressing context)...</div>
      </div>
    </div>
    
    <div v-if="isLoading && !isCompacting" class="message-row role-assistant pending">
      <div class="message-avatar">
        <svg viewBox="0 0 24 24" width="14" height="14" fill="var(--accent)" stroke="none" class="spin"><polygon points="12 2 2 22 22 22"></polygon></svg>
      </div>
      <div class="message-content">
        <div class="message-meta mono-label">AGENT <span class="blink">EXECUTING...</span></div>
        <div class="message-text loader-block"></div>
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
}

.message-row:last-child {
  border-bottom: none;
}

.role-user {
  background: transparent;
}

.role-assistant {
  background: var(--bg-hover);
}

.message-avatar {
  width: 24px;
  height: 24px;
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border: 1px solid var(--border-strong);
  background: var(--bg-app);
}

.role-assistant .message-avatar {
  border-color: transparent;
  background: transparent;
}

.message-content {
  flex: 1;
  min-width: 0;
}

.message-meta {
  margin-bottom: 6px;
  color: var(--text-secondary);
}

.message-text {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-wrap: break-word;
}

.compact-alert {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--text-muted);
  background: rgba(255,255,255,0.05);
  border: 1px solid var(--border-dim);
  padding: 4px 12px;
  border-radius: 12px;
  margin-bottom: 12px;
  margin-left: 40px;
}


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

.spin {
  animation: spin 2s linear infinite;
  opacity: 0.5;
}

.blink {
  animation: blink 1s step-end infinite;
  color: #50E3C2;
  margin-left: 8px;
}

.loader-block {
  width: 120px;
  height: 14px;
  background: var(--border-strong);
  border-radius: 2px;
  animation: pulse 1.5s ease-in-out infinite;
}

.message-text :deep(.code-block) {
  margin: 12px 0;
  background: var(--bg-app);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.message-text :deep(.code-lang) {
  background: var(--bg-hover);
  padding: 6px 12px;
  border-bottom: 1px solid var(--border-dim);
  color: var(--text-muted);
}

.message-text :deep(pre) {
  margin: 0;
  padding: 12px;
  overflow-x: auto;
}

.message-text :deep(code) {
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.5;
}

.message-text :deep(.inline-code) {
  background: var(--bg-hover);
  border: 1px solid var(--border-dim);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--accent);
}

.message-text :deep(.md-table-wrapper) {
  margin: 12px 0;
  overflow-x: auto;
  border: 1px solid var(--border-dim);
  border-radius: var(--radius-sm);
}

.message-text :deep(.md-table) {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  font-family: var(--font-mono);
}

.message-text :deep(.md-table th) {
  text-align: left;
  padding: 8px 12px;
  background: var(--bg-hover);
  border-bottom: 1px solid var(--border-strong);
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  white-space: nowrap;
}

.message-text :deep(.md-table td) {
  padding: 8px 12px;
  border-bottom: 1px solid var(--border-dim);
  color: var(--text-primary);
  line-height: 1.5;
}

.message-text :deep(.md-table tr:last-child td) {
  border-bottom: none;
}

.message-text :deep(.md-table tbody tr:hover) {
  background: var(--bg-hover);
}

.message-text :deep(.md-list) {
  margin: 8px 0;
  padding-left: 20px;
  color: var(--text-primary);
  line-height: 1.7;
}

.message-text :deep(.md-list li) {
  margin-bottom: 4px;
}

.message-text :deep(strong) {
  color: var(--text-primary);
  font-weight: 600;
}

.message-text :deep(em) {
  color: var(--text-secondary);
  font-style: italic;
}

.message-text :deep(hr) {
  border: none;
  border-top: 1px solid var(--border-dim);
  margin: 16px 0;
}

@keyframes spin { 100% { transform: rotate(360deg); } }
@keyframes blink { 50% { opacity: 0; } }
@keyframes pulse { 50% { opacity: 0.4; } }
</style>
