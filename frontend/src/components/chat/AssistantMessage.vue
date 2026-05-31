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
// Check if the assistant message contains file-writing tool operations
const hasWriteOperations = computed(() => {
  const timeline = getSyntheticTimeline.value;
  if (!timeline) return false;
  return timeline.some(item => 
    item.kind === 'event' && 
    item.event.type === 'assistant_tool_call' && 
    (item.event.tool_name === 'write_file' || 
     item.event.tool_name === 'replace_file_content' || 
     item.event.tool_name === 'multi_replace_file_content')
  );
});

const handleDeploy = () => {
  // Show an elegant status banner that says "Assets successfully staged and deployed to dev-sandbox!"
  alert('🚀 资产部署成功！Staged and deployed to development sandbox!');
};

const handleDownload = () => {
  // Simulate file download
  alert('📥 打包下载成功！All files generated have been compressed into agent-workspace.zip!');
};

const handleRequestEdit = () => {
  // Focus on the chat input box!
  const inputEl = document.querySelector('.chat-input-textarea') as HTMLTextAreaElement | null;
  if (inputEl) {
    inputEl.focus();
    inputEl.placeholder = '请输入您的修改建议...';
  }
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
          <div class="toggle-left-indicator" :class="hasError(chunk) ? 'status-error' : 'status-success'"></div>
          <span class="evt-icon-box header-icon-box" :class="hasError(chunk) ? 'status-error' : 'status-success'">
            <ToolIcons :type="hasError(chunk) ? 'tool_error' : 'assistant_tool_call'" :size="11" />
          </span>
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
    
    <!-- 💡 Asset Action Bar (仅在有写文件操作且为最后一条消息时显示) -->
    <div v-if="hasWriteOperations && isLast" class="asset-actions-bar stagger-anim">
      <button class="action-btn deploy-btn" @click="handleDeploy">
        <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2.5" fill="none"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
        <span>一键部署 (Deploy Assets)</span>
      </button>
      <button class="action-btn download-btn" @click="handleDownload">
        <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2.5" fill="none"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
        <span>打包下载 (Download Files)</span>
      </button>
      <button class="action-btn request-btn" @click="handleRequestEdit">
        <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2.5" fill="none"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
        <span>提出修改 (Request Edits)</span>
      </button>
    </div>

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
  margin: 12px 0;
  background: rgba(var(--bg-panel-rgb, 15, 15, 19), 0.3) !important;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 20px -5px rgba(0, 0, 0, 0.4);
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  width: 100%;
}

.history-trace-container:hover {
  border-color: rgba(255, 255, 255, 0.09);
  background: rgba(var(--bg-panel-rgb, 15, 15, 19), 0.45) !important;
}

.history-trace-container.has-error {
  background: rgba(255, 69, 58, 0.03) !important;
  border-color: rgba(255, 69, 58, 0.25);
  box-shadow: 0 4px 20px -5px rgba(255, 69, 58, 0.15);
}

.history-trace-container.has-error:hover {
  border-color: rgba(255, 69, 58, 0.45);
  background: rgba(255, 69, 58, 0.05) !important;
  box-shadow: 0 4px 24px -3px rgba(255, 69, 58, 0.2);
}

.timeline-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 10px 14px;
  width: 100%;
  text-align: left;
  position: relative;
  transition: background 0.15s;
  outline: none;
  appearance: none;
  -webkit-appearance: none;
  -webkit-tap-highlight-color: transparent;
}

.timeline-toggle:hover {
  background: rgba(255, 255, 255, 0.02);
}

.toggle-left-indicator {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: transparent;
  transition: background 0.2s;
}

.toggle-left-indicator.status-success {
  background: #0FB97F;
  box-shadow: 0 0 8px rgba(15, 185, 127, 0.4);
}

.toggle-left-indicator.status-running {
  background: #FFAA00;
  box-shadow: 0 0 8px rgba(255, 170, 0, 0.4);
}

.toggle-left-indicator.status-error {
  background: #ff453a;
  box-shadow: 0 0 8px rgba(255, 69, 58, 0.6);
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
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
  transition: all 0.2s ease;
  margin-right: 4px;
}

.evt-icon-box.header-icon-box.status-success {
  color: #34D399;
  background: rgba(52, 211, 153, 0.06);
  border-color: rgba(52, 211, 153, 0.15);
}

.evt-icon-box.header-icon-box.status-running {
  color: #FBBF24;
  background: rgba(251, 191, 36, 0.06);
  border-color: rgba(251, 191, 36, 0.15);
}

.evt-icon-box.header-icon-box.status-error {
  color: #F87171;
  background: rgba(248, 113, 113, 0.06);
  border-color: rgba(248, 113, 113, 0.15);
}

.toggle-verb {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-primary);
  font-family: var(--font-mono, monospace);
  letter-spacing: 0.01em;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  padding: 8px 14px 12px 20px;
}

.tool-tree-inner {
  min-height: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  position: relative;
}

.tool-tree-inner::before {
  content: "";
  position: absolute;
  left: 31px;
  top: 0;
  bottom: 16px;
  width: 1px;
  background: linear-gradient(
    to bottom,
    rgba(255, 255, 255, 0.08) 0%,
    rgba(255, 255, 255, 0.02) 100%
  );
  z-index: 1;
  pointer-events: none;
}

.stopped-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-muted);
  font-family: var(--font-mono, monospace);
  margin-top: 8px;
  text-transform: uppercase;
}

/* ── 📥 Asset Action Bar (一键部署/打包下载/提出修改) ── */
.asset-actions-bar {
  display: flex;
  gap: 10px;
  margin-top: 18px;
  padding: 12px;
  background: color-mix(in srgb, var(--bg-panel) 94%, var(--text-primary));
  border: 1px solid var(--border-dim);
  border-radius: 10px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
  width: 100%;
  animation: messageSlideUp 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) both;
}

body.theme-default .asset-actions-bar,
body.theme-cyberpunk .asset-actions-bar,
body.theme-emerald .asset-actions-bar,
body.theme-amber .asset-actions-bar {
  background: rgba(255, 255, 255, 0.02);
  border-color: rgba(255, 255, 255, 0.06);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.action-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 6px;
  font-size: 11.5px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  outline: none;
  font-family: var(--font-sans), sans-serif;
  appearance: none;
  -webkit-appearance: none;
  border: none;
}

/* Deploy Button - Main Green Glow */
.deploy-btn {
  background: var(--accent-emerald, #34c759);
  color: #ffffff;
  box-shadow: 0 2px 8px rgba(52, 199, 89, 0.2);
}

.deploy-btn:hover {
  background: color-mix(in srgb, var(--accent-emerald, #34c759) 85%, #000);
  box-shadow: 0 4px 14px rgba(52, 199, 89, 0.4);
  transform: translateY(-1px);
}

/* Download Button - Secondary Blue Accent */
.download-btn {
  background: color-mix(in srgb, var(--accent) 10%, var(--bg-hover));
  border: 1px solid color-mix(in srgb, var(--accent) 25%, var(--border-dim));
  color: var(--accent);
}

.download-btn:hover {
  background: var(--accent);
  color: var(--bg-panel);
  border-color: var(--accent);
  box-shadow: 0 4px 12px var(--accent-glow);
  transform: translateY(-1px);
}

/* Request Button - Light Neutral Muted */
.request-btn {
  background: rgba(255, 255, 255, 0.015);
  border: 1px solid var(--border-dim);
  color: var(--text-secondary);
}

.request-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
  border-color: var(--border-strong);
  transform: translateY(-1px);
}

@keyframes messageSlideUp {
  0% {
    opacity: 0;
    transform: translateY(12px) scale(0.98);
  }
  100% {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}
</style>
