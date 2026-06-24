<script setup lang="ts">
import { computed } from 'vue';
import type { ApprovalInfo } from '../../types';
import type { TimelineChunk, MergedTimelineItem, ThinkingSegment } from './types';
import { findPendingApprovalForTool } from '../../utils/approvalQueue';
import ToolTree from './ToolTree.vue';

const props = defineProps<{
  chunk: TimelineChunk;
  isCollapsed: boolean;
  isAwaitingApproval?: boolean;
  pendingApprovalInfo?: ApprovalInfo | null;
  pendingApprovalInfos?: ApprovalInfo[];
  isProcessingApproval?: boolean;
  isThinkingActive?: boolean;
}>();

const emit = defineEmits<{
  (e: 'toggle'): void;
  (e: 'approve', approvalId?: string): void;
  (e: 'reject', approvalId?: string): void;
  (e: 'approve-all'): void;
}>();

// 统计 thinking chunk 内所有 tool 段的执行次数（用于 header 显示）
const countThinkingTools = computed((): number => {
  if (props.chunk.type !== 'thinking' || !props.chunk.segments) return 0;
  return props.chunk.segments
    .filter((s: ThinkingSegment) => s.kind === 'tools')
    .flatMap((s: ThinkingSegment) => (s as { kind: 'tools'; items: MergedTimelineItem[] }).items)
    .reduce((acc: number, item: MergedTimelineItem) =>
      acc + (item.kind === 'event_group' ? item.count : item.event.type === 'assistant_tool_call' ? 1 : 0), 0);
});

// 判断本思考块内是否包含当前等待审批的工具（控制黄色 WAITING badge）
const hasPendingApprovalInChunk = computed(() => {
  const pendingApprovals = props.pendingApprovalInfos ?? (props.pendingApprovalInfo ? [props.pendingApprovalInfo] : []);
  if (!props.isAwaitingApproval || pendingApprovals.length === 0) return false;
  if (props.chunk.type !== 'thinking' || !props.chunk.segments) return false;
  
  return props.chunk.segments.some((seg: ThinkingSegment) => {
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
});
</script>

<template>
  <div v-if="chunk.type === 'thinking'" class="thinking-container">
    <button class="timeline-toggle" @click="emit('toggle')">
      <span v-if="isThinkingActive" class="thinking-active-pill">
        <span class="thinking-heartbeat"></span>
        思考中...
      </span>
      <span v-else class="toggle-verb thinking-verb">思考过程</span>
      
      <!-- 如果包含挂起审批，增加醒目的橙色指示器 -->
      <span v-if="hasPendingApprovalInChunk" class="pending-warning-pill font-mono">
        <span class="pulse-dot-amber"></span>
        WAITING APPROVAL
      </span>

      <svg class="toggle-chevron" :class="{ open: !isCollapsed }" viewBox="0 0 24 24" width="11" height="11" stroke="currentColor" stroke-width="2.5" fill="none">
        <polyline points="6 9 12 15 18 9"/>
      </svg>
    </button>
    
    <!-- CSS Grid 高定制平滑高度过渡容器 -->
    <div class="tool-tree-wrapper" :class="{ expanded: !isCollapsed }">
      <div class="tool-tree-inner">
        <!-- 按 segments 顺序交替渲染思考文字和工具调用 -->
        <template v-if="chunk.segments && chunk.segments.length > 0">
          <template v-for="(seg, si) in chunk.segments" :key="si">
            <div v-if="seg.kind === 'text'" class="thinking-text">{{ seg.content }}</div>
            <div v-else-if="seg.kind === 'tools'" class="thinking-embedded-tools">
              <ToolTree
                :items="seg.items"
                :isAwaitingApproval="isAwaitingApproval"
                :pendingApprovalInfo="pendingApprovalInfo"
                :pendingApprovalInfos="pendingApprovalInfos"
                :isProcessingApproval="isProcessingApproval"
                @approve="emit('approve', $event)"
                @reject="emit('reject', $event)"
                @approve-all="emit('approve-all')"
              />
            </div>
          </template>
        </template>
        <div v-else class="thinking-text">{{ chunk.content }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.thinking-container {
  margin: 6px 0 8px;
  width: 100%;
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
  font-family: inherit;
  color: var(--text-muted);
  appearance: none;
  -webkit-appearance: none;
  box-shadow: none;
}

.timeline-toggle:hover {
  color: var(--text-secondary);
}

.thinking-heartbeat {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent-emerald, #34D399);
  box-shadow: 0 0 6px var(--accent-emerald, #34D399);
  display: inline-block;
  margin-right: 2px;
  animation: heartbeatPulse 2.2s infinite ease-in-out;
  flex-shrink: 0;
}

.thinking-active-pill {
  font-size: 11px;
  font-weight: 600;
  color: var(--accent-emerald, #34D399);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.thinking-verb {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: inherit;
}

.pending-warning-pill {
  font-size: 9px;
  font-weight: 700;
  color: var(--warning-amber, #FBBF24);
  background: rgba(251, 191, 36, 0.1);
  border: 1px solid rgba(251, 191, 36, 0.15);
  padding: 2px 6px;
  border-radius: 4px;
  margin-left: 8px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.pulse-dot-amber {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--warning-amber, #FBBF24);
  box-shadow: 0 0 6px var(--warning-amber, #FBBF24);
  animation: dotPulse 1.6s infinite ease-in-out;
}

.toggle-chevron {
  color: var(--text-muted);
  transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
  flex-shrink: 0;
  margin-left: auto;
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

.thinking-text {
  font-size: 13.5px;
  color: var(--text-secondary);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  padding: 6px 0 8px 0;
  background: transparent;
  border: none;
  border-radius: 0;
  opacity: 0.85;
}

.thinking-embedded-tools {
  margin-top: 4px;
  padding-top: 4px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

@keyframes heartbeatPulse {
  0%, 100% {
    transform: scale(0.85);
    opacity: 0.6;
    box-shadow: 0 0 4px var(--accent-emerald, #34D399);
  }
  50% {
    transform: scale(1.15);
    opacity: 1;
    box-shadow: 0 0 8px var(--accent-emerald, #34D399);
  }
}

@keyframes dotPulse {
  0%, 100% {
    transform: scale(0.9);
    opacity: 0.6;
  }
  50% {
    transform: scale(1.15);
    opacity: 1;
  }
}
</style>
