<script setup lang="ts">
import { computed, ref } from 'vue';
import type { AgentMessage, TraceRunSummary, StreamingItem, ApprovalInfo } from '../../types';
import type { TimelineChunk, MergedTimelineItem, ThinkingSegment } from './types';
import { formatContent } from '../../utils/formatContent';
import ThinkingBlock from './ThinkingBlock.vue';
import ToolTree from './ToolTree.vue';
import ToolIcons from '../common/ToolIcons.vue';

const props = defineProps<{
  message: AgentMessage;
  msgIndex: number;
  isLast: boolean;
  traceRuns?: TraceRunSummary[];
  lastCompletedRun?: TraceRunSummary | null;
  isAwaitingApproval?: boolean;
  pendingApprovalInfo?: ApprovalInfo | null;
  isProcessingApproval?: boolean;
}>();

const emit = defineEmits<{
  (e: 'approve'): void;
  (e: 'reject'): void;
  (e: 'approve-all'): void;
}>();

const mergeThreshold = 2; // >=2次同名调用折叠
const nonCollapsibleToolNames = new Set([
  'write_file',
  'delete_file',
  'replace_in_file',
  'rename_file',
  'move_file',
  'copy_file',
]);

const collapsedChunks = ref<Record<string, boolean>>({});
const toggleChunk = (id: string) => {
  collapsedChunks.value = { ...collapsedChunks.value, [id]: !(collapsedChunks.value[id] ?? true) };
};

const buildMergedItems = (events: any[]): MergedTimelineItem[] => {
  const items: MergedTimelineItem[] = [];
  let cg: { tool_name: string; events: any[] } | null = null;
  
  const flushG = () => {
    if (!cg) return;
    const callCount = cg.events.filter(e => e.type === 'assistant_tool_call').length;
    const shouldCollapse =
      !nonCollapsibleToolNames.has(cg.tool_name) && callCount >= mergeThreshold;
    if (!shouldCollapse) {
      cg.events.forEach(e => items.push({ kind: 'event', event: e }));
    } else {
      items.push({ kind: 'event_group', tool_name: cg.tool_name, count: callCount, raw_events: cg.events });
    }
    cg = null;
  };
  
  for (const e of events) {
    if (e.type === 'final_answer') continue;
    const tName = e.tool_name || e.type;
    if (!cg) {
      cg = { tool_name: tName, events: [e] };
    } else if (cg.tool_name === tName) {
      cg.events.push(e);
    } else {
      flushG();
      cg = { tool_name: tName, events: [e] };
    }
  }
  flushG();
  return items;
};

const chunkTimeline = computed((): TimelineChunk[] => {
  const timeline = getSyntheticTimeline.value;
  if (!timeline) return [];
  
  const chunks: TimelineChunk[] = [];
  type RawSegment = { kind: 'text'; content: string } | { kind: 'tools'; events: any[] };
  let thinkingSegments: RawSegment[] = [];
  let inThinking = false;
  let currentStandaloneTools: any[] = [];
  let currentText = '';

  const flushThinking = () => {
    if (thinkingSegments.length === 0) return;
    const allText = thinkingSegments.filter(s => s.kind === 'text').map(s => s.content).join('');
    const segments: ThinkingSegment[] = thinkingSegments.map(seg => {
      if (seg.kind === 'text') return { kind: 'text', content: seg.content };
      return { kind: 'tools', items: buildMergedItems(seg.events) };
    });
    chunks.push({
      type: 'thinking',
      content: allText,
      id: `msg-${props.msgIndex}-thinking-${chunks.length}`,
      segments
    });
    thinkingSegments = [];
    inThinking = false;
  };

  const flushStandaloneTools = () => {
    if (currentStandaloneTools.length === 0) return;
    const items = buildMergedItems(currentStandaloneTools);
    if (items.length > 0) {
      chunks.push({
        type: 'tools',
        items,
        raw_count: items.reduce((acc: number, item: MergedTimelineItem) => acc + (item.kind === 'event_group' ? item.raw_events.length : 1), 0),
        id: `msg-${props.msgIndex}-tools-${chunks.length}`
      });
    }
    currentStandaloneTools = [];
  };
  
  for (const item of timeline) {
    if (item.kind === 'thinking') {
      if (inThinking) {
        flushThinking();
      }
      flushStandaloneTools();
      if (currentText.length > 0) {
        chunks.push({ type: 'text', content: currentText, id: `msg-${props.msgIndex}-text-${chunks.length}` });
        currentText = '';
      }
      inThinking = true;
      thinkingSegments.push({ kind: 'text', content: item.content });
    } else if (item.kind === 'text') {
      flushThinking();
      flushStandaloneTools();
      currentText += item.content;
    } else {
      if (currentText.length > 0) {
        chunks.push({ type: 'text', content: currentText, id: `msg-${props.msgIndex}-text-${chunks.length}` });
        currentText = '';
      }
      if (inThinking) {
        const lastSeg = thinkingSegments.at(-1);
        if (lastSeg && lastSeg.kind === 'tools') {
          lastSeg.events.push(item.event);
        } else {
          thinkingSegments.push({ kind: 'tools', events: [item.event] });
        }
      } else {
        currentStandaloneTools.push(item.event);
      }
    }
  }
  
  flushThinking();
  flushStandaloneTools();
  if (currentText.length > 0) {
    chunks.push({ type: 'text', content: currentText, id: `msg-${props.msgIndex}-text-${chunks.length}` });
  }
  
  return chunks;
});

const getSyntheticTimeline = computed((): StreamingItem[] => {
  if (props.message.timeline && props.message.timeline.length > 0) {
    return props.message.timeline;
  }
  
  const r = findRun.value;
  const items: StreamingItem[] = [];
  
  if (r && r.events) {
    r.events.forEach(e => {
      items.push({ kind: 'event', event: e });
    });
  }
  
  if (props.message.content) {
    items.push({ kind: 'text', content: props.message.content });
  }
  
  return items;
});

const findRun = computed((): TraceRunSummary | undefined => {
  if (props.isLast && props.lastCompletedRun) return props.lastCompletedRun;
  
  // 按照 parent 的上下文解析对应的 run
  // 这一步由 traceRuns 进行顺序对齐
  if (props.traceRuns && props.msgIndex >= 0 && props.traceRuns.length > props.msgIndex) {
    return props.traceRuns[props.msgIndex];
  }
  return undefined;
});

const getToolNamesList = (chunk: TimelineChunk): string => {
  if (chunk.type !== 'tools') return '';
  const names = new Set<string>();
  chunk.items.forEach((item: MergedTimelineItem) => {
    if (item.kind === 'event') {
      if (item.event.tool_name) names.add(item.event.tool_name);
    } else if (item.kind === 'event_group') {
      names.add(item.tool_name);
    }
  });
  return Array.from(names).join(', ') || '工具组件';
};

const hasError = (chunk: TimelineChunk): boolean => {
  if (chunk.type !== 'tools') return false;
  return chunk.items.some((item: MergedTimelineItem) => {
    if (item.kind === 'event') {
      return item.event.type === 'tool_error' || (item.event.type === 'tool_result' && item.event.tool_result?.ok === false);
    }
    return false;
  });
};

const hasPendingApprovalInChunk = (chunk: TimelineChunk): boolean => {
  if (!props.isAwaitingApproval || !props.pendingApprovalInfo) return false;
  
  if (chunk.type === 'thinking' && chunk.segments) {
    return chunk.segments.some((seg: ThinkingSegment) => {
      if (seg.kind !== 'tools') return false;
      return seg.items.some((item: MergedTimelineItem) => {
        const pInfo = props.pendingApprovalInfo!;
        if (item.kind === 'event') {
          const cid = item.event.tool_call_id;
          if (cid && cid === pInfo.tool_call_id) return true;
          if (!cid && item.event.tool_name === pInfo.tool_name) return true;
        } else if (item.kind === 'event_group') {
          return item.tool_name === pInfo.tool_name;
        }
        return false;
      });
    });
  }
  
  if (chunk.type === 'tools' && chunk.items) {
    return chunk.items.some((item: MergedTimelineItem) => {
      const pInfo = props.pendingApprovalInfo!;
      if (item.kind === 'event') {
        const cid = item.event.tool_call_id;
        if (cid && cid === pInfo.tool_call_id) return true;
        if (!cid && item.event.tool_name === pInfo.tool_name) return true;
      } else if (item.kind === 'event_group') {
        return item.tool_name === pInfo.tool_name;
      }
      return false;
    });
  }
  
  return false;
};

const isChunkCollapsed = (chunk: TimelineChunk) => {
  const id = chunk.id;
  if (collapsedChunks.value[id] !== undefined) {
    return collapsedChunks.value[id];
  }
  
  // If there's a pending approval in this chunk, auto-expand it!
  if (hasPendingApprovalInChunk(chunk)) {
    return false;
  }
  
  // Default to collapsed (true)
  return true;
};

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
  <div class="assistant-message-content">
    <template v-for="chunk in chunkTimeline" :key="chunk.id">
      <!-- 渲染文本 Chunk -->
      <div 
        v-if="chunk.type === 'text'" 
        class="message-text" 
        v-html="formatContent(chunk.content)" 
        @click="handleCodeBlockClick"
      ></div>
      
      <!-- 渲染思考过程 -->
      <ThinkingBlock
        v-else-if="chunk.type === 'thinking'"
        :chunk="chunk"
        :isCollapsed="isChunkCollapsed(chunk)"
        :isAwaitingApproval="isAwaitingApproval"
        :pendingApprovalInfo="pendingApprovalInfo"
        :isProcessingApproval="isProcessingApproval"
        @toggle="toggleChunk(chunk.id)"
        @approve="emit('approve')"
        @reject="emit('reject')"
        @approve-all="emit('approve-all')"
      />
      
      <!-- 渲染独立工具链 -->
      <div 
        v-else-if="chunk.type === 'tools'" 
        class="history-trace-container" 
        :class="{ 'has-error': hasError(chunk) }"
      >
        <button class="timeline-toggle" @click="toggleChunk(chunk.id)">
          <span class="toggle-verb">
            <template v-if="hasError(chunk)">调用失败: {{ getToolNamesList(chunk) }}</template>
            <template v-else>链式调用: {{ getToolNamesList(chunk) }}</template>
          </span>
          <span class="toggle-count">共 {{ chunk.raw_count }} 步</span>
          <svg class="toggle-chevron" :class="{ open: !isChunkCollapsed(chunk) }" viewBox="0 0 24 24" width="11" height="11" stroke="currentColor" stroke-width="2.5" fill="none">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>

        <div class="tool-tree-wrapper" :class="{ expanded: !isChunkCollapsed(chunk) }">
          <div class="tool-tree-inner">
            <ToolTree
              :items="chunk.items"
              :isAwaitingApproval="isAwaitingApproval"
              :pendingApprovalInfo="pendingApprovalInfo"
              :isProcessingApproval="isProcessingApproval"
              @approve="emit('approve')"
              @reject="emit('reject')"
              @approve-all="emit('approve-all')"
            />
          </div>
        </div>
      </div>
    </template>
    <div v-if="message.stopped" class="stopped-label">⏹ Stopped</div>
  </div>
</template>

<style scoped>
.assistant-message-content {
  width: 100%;
  display: flex;
  flex-direction: column;
}

.message-text {
  font-size: 13.5px;
  line-height: 1.6;
  word-break: break-word;
}

/* ── 链式调用外部 Trace 容器 ── */
.history-trace-container {
  margin: 8px 0;
  background: transparent !important;
  backdrop-filter: none !important;
  -webkit-backdrop-filter: none !important;
  border: none !important;
  border-radius: 0;
  overflow: hidden;
  box-shadow: none !important;
  transition: all 0.2s ease;
  width: 100%;
}

.history-trace-container:hover {
  background: transparent !important;
}

.history-trace-container.has-error {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}

.history-trace-container.has-error:hover {
  background: transparent !important;
}

.timeline-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 6px 0;
  width: 100%;
  text-align: left;
  position: relative;
  transition: all 0.2s ease;
  outline: none;
  appearance: none;
  -webkit-appearance: none;
  -webkit-tap-highlight-color: transparent;
}

.timeline-toggle:hover {
  background: transparent;
}

.toggle-left-indicator {
  display: none;
}

.evt-icon-box.header-icon-box {
  width: 20px;
  height: 20px;
  border-radius: 5px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--text-secondary, #A1A1AA);
  background: transparent !important;
  border: none !important;
  transition: all 0.2s ease;
  margin-right: 4px;
}

.evt-icon-box.header-icon-box.status-success {
  color: #34D399;
}

.evt-icon-box.header-icon-box.status-running {
  color: #FBBF24;
}

.evt-icon-box.header-icon-box.status-error {
  color: #F87171;
}

.toggle-verb {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  font-family: inherit;
  letter-spacing: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.toggle-verb:hover {
  color: var(--text-primary);
}

.toggle-count {
  font-size: 11px;
  font-weight: 500;
  color: var(--text-muted);
  font-family: var(--font-mono, monospace);
  padding: 2px 6px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 4px;
  margin-right: 4px;
}

.toggle-chevron {
  color: var(--text-muted);
  transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
  flex-shrink: 0;
}

.toggle-chevron.open {
  transform: rotate(180deg);
  color: var(--text-secondary);
}

/* --- Smooth CSS Grid Height Transition --- */
.tool-tree-wrapper {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.25s ease, padding 0.25s ease;
  overflow: hidden;
  opacity: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.tool-tree-wrapper.expanded {
  grid-template-rows: 1fr;
  opacity: 1;
  padding: 4px 0 10px 0;
}

.tool-tree-inner {
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  position: relative;
}

.stopped-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  font-family: var(--font-mono, monospace);
  margin-top: 8px;
  text-transform: uppercase;
}
</style>
