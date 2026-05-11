import json
import re

# I will write the base content from the first read_file here, then patch it immediately.
content = """<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue';
import type { AgentMessage, TraceRunSummary, StreamingItem, AgentEvent } from '../types';
import TraceInline from './TraceInline.vue';
import ToolIcons from './common/ToolIcons.vue';

// 连续事件合并逻辑
export type MergedTimelineItem = 
  | { kind: 'text'; content: string }
  | { kind: 'event'; event: AgentEvent }
  | { kind: 'event_group'; tool_name: string; count: number; raw_events: AgentEvent[] }
  | { kind: 'merged_tool_run'; call: AgentEvent; result?: AgentEvent; error?: AgentEvent };

const mergeThreshold = 2; // >=2次完整调用（>=4个事件）开始折叠

const groupTimeline = (timeline: StreamingItem[] | undefined): MergedTimelineItem[] => {
  if (!timeline) return [];
  const result: MergedTimelineItem[] = [];
  let currentGroup: { tool_name: string, events: AgentEvent[] } | null = null;
  
  const flushGroup = () => {
    if (!currentGroup) return;
    const callCount = currentGroup.events.filter(e => e.type === 'assistant_tool_call').length;
    if (callCount < mergeThreshold) {
      currentGroup.events.forEach(e => result.push({ kind: 'event', event: e }));
    } else {
      result.push({
        kind: 'event_group',
        tool_name: currentGroup.tool_name,
        count: callCount,
        raw_events: currentGroup.events
      });
    }
    currentGroup = null;
  };

  for (const item of timeline) {
    if (item.kind === 'text') {
      flushGroup();
      result.push({ kind: 'text', content: item.content });
    } else {
      const event = item.event;
      const tName = event.tool_name || event.type;
      if (!currentGroup) {
        currentGroup = { tool_name: tName, events: [event] };
      } else {
        if (currentGroup.tool_name === tName) {
          currentGroup.events.push(event);
        } else {
          flushGroup();
          currentGroup = { tool_name: tName, events: [event] };
        }
      }
    }
  }
  flushGroup();
  return result;
};

// 每条消息的工具事件折叠状态（key = 消息在列表中的 index）
const eventsCollapsed = ref<Record<number, boolean>>({});
const toggleEvents = (idx: number) => {
  eventsCollapsed.value = { ...eventsCollapsed.value, [idx]: !eventsCollapsed.value[idx] };
};
const isCollapsed = (idx: number) => eventsCollapsed.value[idx] ?? true;  // 默认收起

// timeline 中工具事件数量
const timelineEventCount = (tl: StreamingItem[]) => tl.filter(i => i.kind === 'event').length;

const props = defineProps<{
  messages: AgentMessage[];
  isLoading: boolean;
  isCompacting?: boolean;
  traceRuns?: TraceRunSummary[];
  isStreaming?: boolean;
  streamingTimeline?: StreamingItem[];        // 按到达顺序混排的文字和工具事件
  lastCompletedRun?: TraceRunSummary | null;
}>();

// 是否有工具调用
const hasToolEvents = (run: TraceRunSummary): boolean =>
  run.events.some(e => e.type === 'assistant_tool_call' || e.type === 'tool_result' || e.type === 'tool_error');

const findRun = (msgIndex: number, isLast: boolean): TraceRunSummary | undefined => {
  if (isLast && props.lastCompletedRun) return props.lastCompletedRun;
  for (let i = msgIndex - 1; i >= 0; i--) {
    if (props.messages[i]?.role === 'user') {
      const userText = (props.messages[i].content ?? '').trim();
      return props.traceRuns?.find(r => r.user_input.trim() === userText);
    }
  }
  return undefined;
};

const listRef = ref<HTMLElement | null>(null);

const visibleMessages = computed(() =>
  props.messages.filter((message) => 
    message.role === 'user' || 
    (message.role === 'assistant' && !!message.content) ||
    (message.role === 'system' && (message.content?.includes('[COMPACT_SUMMARY]') || message.content?.includes('[RESET_MARKER]')))
  )
);

watch([() => visibleMessages.value.length, () => props.isLoading, () => props.isCompacting, () => props.streamingTimeline?.length], async () => {
  await nextTick();
  if (listRef.value) {
    listRef.value.scrollTop = listRef.value.scrollHeight;
  }
}, { deep: true });

const formatContent = (text: string | null) => {
  if (!text) return '';
  text = text.replace('[COMPACT_SUMMARY]\\nThe following is a compressed summary of the middle part of the conversation. It is not a verbatim transcript. Preserve task goals, constraints, important tool results, and unfinished work.\\n\\n', '');
  
  let html = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  
  html = html.replace(/```([\\w-]*)\\n([\\s\\S]*?)```/g, (_match, lang, code) => {
    const langLabel = lang ? `<div class="code-lang mono-label">${lang}</div>` : '';
    return `<div class="code-block">${langLabel}<pre><code>${code}</code></pre></div>`;
  });

  html = html.replace(/((?:^\\|.+\\|$\\n?){2,})/gm, (tableBlock) => {
    const rows = tableBlock.trim().split('\\n').filter(r => r.trim());
    if (rows.length < 2) return tableBlock; 
    const sepLine = rows[1];
    if (!/^\\|[\\s-:|]+\\|$/.test(sepLine)) return tableBlock; 

    const parseRow = (row: string) => row.split('|').slice(1, -1).map(cell => cell.trim()); 
    const headerCells = parseRow(rows[0]);
    const bodyRows = rows.slice(2); 

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
  
  html = html.replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>');
  html = html.replace(/^---+$/gm, '<hr style="border:none;border-top:1px solid var(--border-dim);margin:12px 0;">');
  html = html.replace(/^### (.+)$/gm, '<div style="font-size:13px;font-weight:600;color:var(--text-primary);margin:10px 0 4px;">$1</div>');
  html = html.replace(/^## (.+)$/gm, '<div style="font-size:14px;font-weight:600;color:var(--text-primary);margin:12px 0 4px;">$1</div>');
  html = html.replace(/^# (.+)$/gm, '<div style="font-size:15px;font-weight:700;color:var(--text-primary);margin:14px 0 4px;">$1</div>');
  html = html.replace(/\\*\\*([^\\*]+)\\*\\*/g, '<strong>$1</strong>');
  html = html.replace(/(?<!\\*)\\*(?!\\*)([^\\*]+)(?<!\\*)\\*(?!\\*)/g, '<em>$1</em>');

  html = html.replace(/((?:^- .+$\\n?)+)/gm, (block) => {
    const items = block.trim().split('\\n').filter(l => l.trim().startsWith('- ')).map(l => `<li>${l.replace(/^- /, '')}</li>`);
    return `<ul class="md-list">${items.join('')}</ul>`;
  });

  html = html.replace(/((?:^\\d+\\. .+$\\n?)+)/gm, (block) => {
    const items = block.trim().split('\\n').filter(l => /^\\d+\\. /.test(l.trim())).map(l => `<li>${l.replace(/^\\d+\\. /, '')}</li>`);
    return `<ol class="md-list">${items.join('')}</ol>`;
  });

  return html;
};
</script>

<template>
  <div v-if="visibleMessages.length === 0 && !isCompacting" class="message-list empty"></div>
  <div v-else class="message-list" ref="listRef">
    <div v-for="(m, idx) in visibleMessages" :key="idx" :class="['message-row', `role-${m.role}`]">
      <template v-if="m.role === 'system'">
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
          <svg v-else class="ai-avatar glow" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l3 6.5 7 1-5 4.5 1.5 7-6.5-3.5-6.5 3.5 1.5-7-5-4.5 7-1z"></path></svg>
        </div>
        <div class="message-content">
          <div class="message-meta mono-label">{{ m.role === 'user' ? 'USER' : 'AGENT' }}</div>
          
          <template v-if="m.role === 'assistant' && m.timeline && m.timeline.length > 0">
            <template v-for="(item, ti) in groupTimeline(m.timeline)" :key="ti">
              <div v-if="item.kind === 'text'" class="message-text" v-html="formatContent(item.content)"></div>
              
              <template v-else-if="item.kind === 'event' || item.kind === 'event_group'">
                <!-- 依然可以在第一个工具调用处放折叠开关 -->
                <button v-if="ti === groupTimeline(m.timeline).findIndex((x: any) => x.kind.startsWith('event'))" class="timeline-toggle" @click="toggleEvents(idx)">
                  <span class="timeline-toggle-arrow" :class="{ open: !isCollapsed(idx) }">›</span>
                  <span class="mono-label">工具调用</span>
                  <span class="mono-label" style="color:var(--text-muted)">{{ timelineEventCount(m.timeline) }} 步</span>
                </button>
                
                <div v-if="item.kind === 'event'" class="stream-event-row stagger-anim" :class="[`evt-${item.event.type}`, { 'evt-hidden': isCollapsed(idx) }]" :style="{ animationDelay: `${ti * 0.05}s` }">
                  <span class="evt-icon"><ToolIcons :type="item.event.type"/></span>
                  <span class="evt-label mono-label">{{ item.event.tool_name ?? item.event.type }}</span>
                  <span v-if="item.event.content" class="evt-content">{{ item.event.content.replace(/\\n/g,' ').slice(0, 80) }}{{ item.event.content.length > 80 ? '…' : '' }}</span>
                </div>
                
                <div v-else-if="item.kind === 'event_group'" class="stream-event-row evt-group stagger-anim" :class="[{ 'evt-hidden': isCollapsed(idx) }]" :style="{ animationDelay: `${ti * 0.05}s` }">
                  <span class="evt-icon"><ToolIcons type="assistant_tool_call"/></span>
                  <span class="evt-label mono-label">{{ item.tool_name }}</span>
                  <span class="evt-content" style="font-weight: 500; font-style: italic;">连续执行了 {{ item.count }} 次 (Grouped {{ item.raw_events.length }} events)</span>
                </div>
              </template>
            </template>
          </template>

          <template v-else>
            <div class="message-text" v-html="formatContent(m.content)"></div>
            <TraceInline v-if="m.role === 'assistant' && (() => { const r = findRun(idx, idx === visibleMessages.length - 1); return r && hasToolEvents(r) ? r : null })()" :events="findRun(idx, idx === visibleMessages.length - 1)!.events" />
          </template>
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
    
    <div v-if="isStreaming" class="message-row role-assistant pending">
      <div class="message-avatar">
        <svg class="ai-avatar spin glow" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l3 6.5 7 1-5 4.5 1.5 7-6.5-3.5-6.5 3.5 1.5-7-5-4.5 7-1z"></path></svg>
      </div>
      <div class="message-content">
        <div class="message-meta mono-label">AGENT <span class="blink">STREAMING...</span></div>

        <template v-if="streamingTimeline && streamingTimeline.length > 0">
          <template v-for="(item, i) in groupTimeline(streamingTimeline)" :key="i">
            <div v-if="item.kind === 'text'" class="message-text" v-html="formatContent(item.content)"></div>
            <div v-else-if="item.kind === 'event'" class="stream-event-row stagger-anim" :class="`evt-${item.event.type}`">
              <span class="evt-icon"><ToolIcons :type="item.event.type"/></span>
              <span class="evt-label mono-label">{{ item.event.tool_name ?? item.event.type }}</span>
              <span v-if="item.event.content" class="evt-content">{{ item.event.content.replace(/\\n/g,' ').slice(0, 80) }}{{ item.event.content.length > 80 ? '…' : '' }}</span>
            </div>
            <div v-else-if="item.kind === 'event_group'" class="stream-event-row evt-group stagger-anim">
              <span class="evt-icon"><ToolIcons type="assistant_tool_call"/></span>
              <span class="evt-label mono-label">{{ item.tool_name }}</span>
              <span class="evt-content" style="font-weight: 500; font-style: italic;">连续执行了 {{ item.count }} 次...</span>
            </div>
          </template>
        </template>
        <div v-else class="message-text loader-block"></div>
      </div>
    </div>

    <div v-if="isLoading && !isStreaming && !isCompacting" class="message-row role-assistant pending">
      <div class="message-avatar">
        <svg class="ai-avatar spin glow" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l3 6.5 7 1-5 4.5 1.5 7-6.5-3.5-6.5 3.5 1.5-7-5-4.5 7-1z"></path></svg>
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

/* AI Avatar styles */
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

.stream-event-row {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 4px 0;
  font-size: 12px;
  border-left: 2px solid var(--border-strong);
  padding-left: 8px;
  margin: 3px 0;
  opacity: 0.85;
  overflow: hidden;
  max-height: 40px;
  transition: max-height 0.2s ease, opacity 0.2s ease, margin 0.2s ease, padding 0.2s ease;
}

.stream-event-row.evt-group {
  border-left: 2px solid var(--accent);
  background: var(--bg-active);
  border-radius: 4px;
  padding: 6px 10px;
  margin-left: -2px;
}

.stream-event-row.evt-hidden {
  max-height: 0;
  opacity: 0;
  margin: 0;
  padding-top: 0;
  padding-bottom: 0;
}
</style>
"""

with open("src/components/MessageList.vue", "w") as f:
    f.write(content)

