<script setup lang="ts">
import { computed, ref } from 'vue';
import type { AgentMessage, TraceRunSummary, StreamingItem, ApprovalInfo } from '../../types';
import type { TimelineChunk, MergedTimelineItem, ThinkingSegment } from './types';
import { formatContent } from '../../utils/formatContent';
import { findPendingApprovalForTool } from '../../utils/approvalQueue';
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
  pendingApprovalInfos?: ApprovalInfo[];
  isProcessingApproval?: boolean;
}>();

const emit = defineEmits<{
  (e: 'approve', approvalId?: string): void;
  (e: 'reject', approvalId?: string): void;
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
    if (e.type === 'assistant_text' || e.type === 'final_answer' || e.type === 'thinking') continue;
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
  
  // 优先用 run_id 精确匹配，避免 visibleMessages 下标与 traceRuns 下标错位
  if (props.message.run_id && props.traceRuns) {
    const byId = props.traceRuns.find(r => r.run_id === props.message.run_id);
    if (byId) return byId;
  }

  // 降级：按 traceRuns 顺序对齐（仅在无 run_id 时兜底）
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
  const pendingApprovals = props.pendingApprovalInfos ?? (props.pendingApprovalInfo ? [props.pendingApprovalInfo] : []);
  if (!props.isAwaitingApproval || pendingApprovals.length === 0) return false;
  
  if (chunk.type === 'thinking' && chunk.segments) {
    return chunk.segments.some((seg: ThinkingSegment) => {
      if (seg.kind !== 'tools') return false;
      return seg.items.some((item: MergedTimelineItem) => {
        if (item.kind === 'event') {
          return !!findPendingApprovalForTool(
            pendingApprovals,
            item.event.tool_call_id,
            item.event.tool_name,
            item.event.type === 'approval_required' ? item.event.content : null,
          );
        } else if (item.kind === 'event_group') {
          return item.raw_events.some(event => !!findPendingApprovalForTool(
            pendingApprovals,
            event.tool_call_id,
            event.tool_name,
            event.type === 'approval_required' ? event.content : null,
          ));
        }
        return false;
      });
    });
  }
  
  if (chunk.type === 'tools' && chunk.items) {
    return chunk.items.some((item: MergedTimelineItem) => {
      if (item.kind === 'event') {
        return !!findPendingApprovalForTool(
          pendingApprovals,
          item.event.tool_call_id,
          item.event.tool_name,
          item.event.type === 'approval_required' ? item.event.content : null,
        );
      } else if (item.kind === 'event_group') {
        return item.raw_events.some(event => !!findPendingApprovalForTool(
          pendingApprovals,
          event.tool_call_id,
          event.tool_name,
          event.type === 'approval_required' ? event.content : null,
        ));
      }
      return false;
    });
  }
  
  return false;
};

const hasRunningToolInChunk = (chunk: TimelineChunk): boolean => {
  const callIds = new Set<string>();
  const finishedIds = new Set<string>();
  
  const checkEvent = (event: any) => {
    if (event.type === 'assistant_tool_call' && event.tool_call_id) {
      callIds.add(event.tool_call_id);
    } else if ((event.type === 'tool_result' || event.type === 'tool_error') && event.tool_call_id) {
      finishedIds.add(event.tool_call_id);
    }
  };

  if (chunk.type === 'tools' && chunk.items) {
    chunk.items.forEach((item: MergedTimelineItem) => {
      if (item.kind === 'event') {
        checkEvent(item.event);
      } else if (item.kind === 'event_group') {
        item.raw_events.forEach(checkEvent);
      }
    });
  } else if (chunk.type === 'thinking' && chunk.segments) {
    chunk.segments.forEach((seg: ThinkingSegment) => {
      if (seg.kind === 'tools') {
        seg.items.forEach((item: MergedTimelineItem) => {
          if (item.kind === 'event') {
            checkEvent(item.event);
          } else if (item.kind === 'event_group') {
            item.raw_events.forEach(checkEvent);
          }
        });
      }
    });
  }

  for (const cid of callIds) {
    if (!finishedIds.has(cid)) {
      return true;
    }
  }
  return false;
};

const isThinkingActive = (chunk: TimelineChunk): boolean => {
  if (props.msgIndex !== 9999) return false;
  if (chunk.type !== 'thinking') return false;
  const hasText = getSyntheticTimeline.value.some(t => t.kind === 'text' && t.content.trim().length > 0);
  return !hasText;
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
  
  // If there's a running tool in this chunk, auto-expand it!
  if (hasRunningToolInChunk(chunk)) {
    return false;
  }

  // If this is the active streaming message...
  if (props.msgIndex === 9999) {
    // If it's a thinking block and the response text has started, auto-collapse it!
    if (chunk.type === 'thinking') {
      const hasText = getSyntheticTimeline.value.some(t => t.kind === 'text' && t.content.trim().length > 0);
      if (hasText) {
        return true;
      }
    }
    return false;
  }
  
  // Default to collapsed (true)
  return true;
};

const toolCnNameMap: Record<string, string> = {
  write_file: 'WRITE',
  replace_file_content: 'WRITE',
  multi_replace_file_content: 'WRITE',
  view_file: 'READ',
  list_dir: 'READ',
  grep_search: 'SEARCH',
  web_search: 'SEARCH',
  run_command: 'RUN',
  invoke_subagent: 'SUBAGENT',
  define_subagent: 'SUBAGENT',
};

const toolRunningNameMap: Record<string, string> = {
  write_file: 'WRITING',
  replace_file_content: 'WRITING',
  multi_replace_file_content: 'WRITING',
  view_file: 'READING',
  list_dir: 'READING',
  grep_search: 'SEARCHING',
  web_search: 'SEARCHING',
  run_command: 'RUNNING',
  invoke_subagent: 'CALLING',
  define_subagent: 'DEFINING',
};

const getFirstToolName = (chunk: TimelineChunk): string | null => {
  if (chunk.type !== 'tools' || !chunk.items || chunk.items.length === 0) return null;
  const first = chunk.items[0];
  if (first.kind === 'event') {
    return first.event.tool_name ?? null;
  } else if (first.kind === 'event_group') {
    return first.tool_name ?? null;
  }
  return null;
};

const timelineNodeLabel = (chunk: TimelineChunk, index: number): string => {
  if (chunk.type === 'thinking') return props.msgIndex === 9999 && isThinkingActive(chunk) ? 'Thinking' : 'Thought';
  if (chunk.type === 'tools') {
    if (hasError(chunk)) return 'Tool Error';
    const rawName = getFirstToolName(chunk);
    if (rawName) {
      const active = isTimelineNodeActive(chunk, index);
      if (active) {
        return toolRunningNameMap[rawName] || rawName.toUpperCase();
      } else {
        return toolCnNameMap[rawName] || rawName.toUpperCase();
      }
    }
    return 'Tool Use';
  }
  return 'Ariadne';
};

const isTimelineNodeActive = (chunk: TimelineChunk, index: number): boolean => {
  if (props.msgIndex !== 9999) return false;
  if (chunk.type === 'thinking') return isThinkingActive(chunk);
  if (chunk.type === 'tools') return hasRunningToolInChunk(chunk) || hasPendingApprovalInChunk(chunk);
  return index === chunkTimeline.value.length - 1;
};

const timelineNodeClass = (chunk: TimelineChunk, index: number) => ({
  'is-active': isTimelineNodeActive(chunk, index),
  'is-error': chunk.type === 'tools' && hasError(chunk),
  'is-tool': chunk.type === 'tools',
  'is-thinking': chunk.type === 'thinking',
  'is-text': chunk.type === 'text',
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
</script>

<template>
  <div class="assistant-message-content">
    <div
      v-for="(chunk, chunkIndex) in chunkTimeline"
      :key="chunk.id"
      class="agent-timeline-node"
      :class="timelineNodeClass(chunk, chunkIndex)"
    >
      <div class="agent-timeline-rail" aria-hidden="true">
        <span class="agent-timeline-marker"></span>
      </div>
      <div class="agent-timeline-body">
        <div class="agent-timeline-label">
          <span>{{ timelineNodeLabel(chunk, chunkIndex) }}</span>
          <span v-if="isTimelineNodeActive(chunk, chunkIndex) && chunk.type === 'text'" class="agent-timeline-running">running</span>
        </div>
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
        :pendingApprovalInfos="pendingApprovalInfos"
        :isProcessingApproval="isProcessingApproval"
        :isThinkingActive="isThinkingActive(chunk)"
        @toggle="toggleChunk(chunk.id)"
        @approve="emit('approve', $event)"
        @reject="emit('reject', $event)"
        @approve-all="emit('approve-all')"
      />
      
      <!-- 渲染独立工具链 -->
      <div 
        v-else-if="chunk.type === 'tools'" 
        class="history-trace-container-flat"
      >
        <div class="tool-tree-inner">
          <ToolTree
            :items="chunk.items"
            :isAwaitingApproval="isAwaitingApproval"
            :pendingApprovalInfo="pendingApprovalInfo"
            :pendingApprovalInfos="pendingApprovalInfos"
            :isProcessingApproval="isProcessingApproval"
            @approve="emit('approve', $event)"
            @reject="emit('reject', $event)"
            @approve-all="emit('approve-all')"
          />
        </div>
      </div>
      </div>
    </div>
    <div v-if="message.stopped" class="stopped-label">Stopped</div>
  </div>
</template>

<style scoped>
.assistant-message-content {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 0;
  position: relative;
}

.agent-timeline-node {
  display: grid;
  grid-template-columns: 18px minmax(0, 1fr);
  column-gap: 8px;
  position: relative;
  animation: nodeIn 0.2s ease both;
}

.agent-timeline-rail {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
  color: var(--text-muted);
  user-select: none;
}

/* Continuous │ line drawn as a CSS border — monospace-width centered */
.agent-timeline-rail::before {
  content: '';
  position: absolute;
  top: 0;
  bottom: 0;
  left: 50%;
  transform: translateX(-0.5px);
  width: 1px;
  background: var(--text-muted);
  opacity: 0.22;
}

/* Hide top connector on first node, bottom on last */
.agent-timeline-node:first-child .agent-timeline-rail::before {
  top: 14px;
}

.agent-timeline-node:last-of-type .agent-timeline-rail::before {
  bottom: calc(100% - 14px);
}

/* Branch marker rendered as a monospace character */
.agent-timeline-marker {
  position: relative;
  z-index: 1;
  width: 14px;
  height: 18px;
  margin-top: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
  font-size: 11px;
  color: var(--text-muted);
  opacity: 0.35;
  flex-shrink: 0;
  /* White background to "cut" the rail line, creating a node point */
  background: var(--bg-app);
}

.agent-timeline-marker::before {
  content: '·';
  font-size: 16px;
  line-height: 1;
}

.agent-timeline-node.is-active .agent-timeline-marker {
  opacity: 1;
  background: var(--bg-app);
}

.agent-timeline-node.is-active .agent-timeline-marker::before {
  content: '▸';
  font-size: 9px;
  color: var(--accent-emerald, #34c759);
  animation: activeMarkerPulse 1.2s ease-in-out infinite;
  will-change: opacity;
}

.agent-timeline-node.is-error .agent-timeline-marker {
  opacity: 1;
}

.agent-timeline-node.is-error .agent-timeline-marker::before {
  content: '✗';
  font-size: 9px;
  color: var(--danger, #ff453a);
}


.agent-timeline-body {
  min-width: 0;
  padding: 0 0 10px;
}

.agent-timeline-label {
  min-height: 18px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--text-muted);
  font-family: var(--font-mono, ui-monospace, SFMono-Regular, Menlo, monospace);
  font-size: 10.5px;
  font-weight: 500;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  opacity: 0.6;
  margin-bottom: 4px;
}

.agent-timeline-node.is-active .agent-timeline-label {
  opacity: 1;
  color: var(--text-secondary);
  animation: activeMarkerPulse 1.8s ease-in-out infinite;
  will-change: opacity;
}

.agent-timeline-running {
  color: var(--accent-emerald, #34c759);
  font-size: 9.5px;
  font-weight: 500;
  letter-spacing: 0.08em;
  opacity: 0.85;
  animation: activeMarkerPulse 1.2s ease-in-out infinite;
  will-change: opacity;
}

@keyframes nodeIn {
  from { opacity: 0; transform: translateY(3px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes activeMarkerPulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

.message-text {
  font-size: 13.5px;
  line-height: 1.65;
  word-break: break-word;
}

/* Tool chain containers */
.history-trace-container-flat {
  margin: 2px 0 0;
  width: 100%;
}

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

.history-trace-container:hover { background: transparent !important; }
.history-trace-container.has-error { background: transparent !important; border: none !important; box-shadow: none !important; }
.history-trace-container.has-error:hover { background: transparent !important; }

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
  outline: none;
  appearance: none;
  -webkit-appearance: none;
  -webkit-tap-highlight-color: transparent;
}

.timeline-toggle:hover { background: transparent; }
.toggle-left-indicator { display: none; }

.evt-icon-box.header-icon-box {
  width: 20px; height: 20px; border-radius: 5px;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
  color: var(--text-secondary, #A1A1AA);
  background: transparent !important; border: none !important;
  transition: all 0.2s ease; margin-right: 4px;
}
.evt-icon-box.header-icon-box.status-success { color: #34D399; }
.evt-icon-box.header-icon-box.status-running { color: #FBBF24; }
.evt-icon-box.header-icon-box.status-error { color: #F87171; }

.toggle-verb {
  font-size: 13px; font-weight: 500; color: var(--text-secondary);
  font-family: inherit; letter-spacing: 0; flex: 1;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.toggle-verb:hover { color: var(--text-primary); }

.toggle-count {
  font-size: 11px; font-weight: 500; color: var(--text-muted);
  font-family: var(--font-mono, monospace);
  padding: 2px 6px; background: rgba(255,255,255,0.04); border-radius: 4px; margin-right: 4px;
}

.toggle-chevron {
  color: var(--text-muted);
  transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
  flex-shrink: 0;
}
.toggle-chevron.open { transform: rotate(180deg); color: var(--text-secondary); }

.tool-tree-wrapper {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.3s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.25s ease, padding 0.25s ease;
  overflow: hidden;
  opacity: 0;
  padding-top: 0;
  padding-bottom: 0;
}
.tool-tree-wrapper.expanded { grid-template-rows: 1fr; opacity: 1; padding: 4px 0 10px 0; }

.tool-tree-inner {
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 1px;
  position: relative;
}

.stopped-label {
  font-size: 10.5px; font-weight: 500; color: var(--text-muted);
  font-family: var(--font-mono, monospace);
  margin-top: 8px; text-transform: uppercase; letter-spacing: 0.06em; opacity: 0.45;
}
</style>
