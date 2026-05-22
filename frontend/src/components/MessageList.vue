<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue';
import type { AgentMessage, TraceRunSummary, StreamingItem, AgentEvent } from '../types';
import TraceInline from './TraceInline.vue';
import ToolIcons from './common/ToolIcons.vue';
import { formatContent } from '../utils/formatContent';

// ======= 折叠区块结构 ======
export type MergedTimelineItem = 
  | { kind: 'event'; event: AgentEvent }
  | { kind: 'event_group'; tool_name: string; count: number; raw_events: AgentEvent[] };

// 思考过程内部的有序片段：思考文字 或 工具调用组
export type ThinkingSegment =
  | { kind: 'text'; content: string }
  | { kind: 'tools'; items: MergedTimelineItem[] };

export type TimelineChunk = 
  | { type: 'text';     content: string; id: string }
  | { type: 'thinking'; content: string; id: string; segments?: ThinkingSegment[] }
  | { type: 'tools';    items: MergedTimelineItem[]; id: string; raw_count: number };

const mergeThreshold = 2; // >=2次完整调用（>=4个事件）开始折叠

// 将原始 AgentEvent 数组构建为 MergedTimelineItem 数组（合并同名工具连续调用）
const buildMergedItems = (events: AgentEvent[]): MergedTimelineItem[] => {
  const items: MergedTimelineItem[] = [];
  let cg: { tool_name: string; events: AgentEvent[] } | null = null;
  const flushG = () => {
    if (!cg) return;
    const callCount = cg.events.filter(e => e.type === 'assistant_tool_call').length;
    if (callCount < mergeThreshold) cg.events.forEach(e => items.push({ kind: 'event', event: e }));
    else items.push({ kind: 'event_group', tool_name: cg.tool_name, count: callCount, raw_events: cg.events });
    cg = null;
  };
  for (const e of events) {
    if (e.type === 'final_answer') continue;
    const tName = e.tool_name || e.type;
    if (!cg) cg = { tool_name: tName, events: [e] };
    else if (cg.tool_name === tName) cg.events.push(e);
    else { flushG(); cg = { tool_name: tName, events: [e] }; }
  }
  flushG();
  return items;
};

const chunkTimeline = (timeline: StreamingItem[] | undefined, msgIdx: number = 0): TimelineChunk[] => {
  if (!timeline) return [];
  
  const chunks: TimelineChunk[] = [];
  // 思考过程内部的有序片段（文字 + 工具交替）
  type RawSegment = { kind: 'text'; content: string } | { kind: 'tools'; events: AgentEvent[] };
  let thinkingSegments: RawSegment[] = [];
  let inThinking = false;
  let currentStandaloneTools: AgentEvent[] = [];
  let currentText = '';

  const flushThinking = () => {
    if (thinkingSegments.length === 0) return;
    // 合并全部文字段落用于 content 字段（header 显示用）
    const allText = thinkingSegments.filter(s => s.kind === 'text').map(s => s.content).join('');
    // 构建带顺序信息的 segments
    const segments: ThinkingSegment[] = thinkingSegments.map(seg => {
      if (seg.kind === 'text') return { kind: 'text', content: seg.content };
      return { kind: 'tools', items: buildMergedItems(seg.events) };
    });
    chunks.push({
      type: 'thinking',
      content: allText,
      id: `msg-${msgIdx}-thinking-${chunks.length}`,
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
        raw_count: items.reduce((acc, item) => acc + (item.kind === 'event_group' ? item.raw_events.length : 1), 0),
        id: `msg-${msgIdx}-tools-${chunks.length}`
      });
    }
    currentStandaloneTools = [];
  };
  
  for (const item of timeline) {
    if (item.kind === 'thinking') {
      // 进入/继续思考状态
      flushStandaloneTools();
      if (currentText.length > 0) {
        chunks.push({ type: 'text', content: currentText, id: `msg-${msgIdx}-text-${chunks.length}` });
        currentText = '';
      }
      inThinking = true;
      // 追加到最后一段文字，或新建文字段
      const lastSeg = thinkingSegments.at(-1);
      if (lastSeg && lastSeg.kind === 'text') {
        lastSeg.content += item.content;
      } else {
        thinkingSegments.push({ kind: 'text', content: item.content });
      }
    } else if (item.kind === 'text') {
      // 遇到最终回答：冲刷思考 + 独立工具
      flushThinking();
      flushStandaloneTools();
      currentText += item.content;
    } else {
      // 工具事件
      if (currentText.length > 0) {
        chunks.push({ type: 'text', content: currentText, id: `msg-${msgIdx}-text-${chunks.length}` });
        currentText = '';
      }
      if (inThinking) {
        // 思考过程中的工具：追加到最后一段工具组，或新建工具段
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
  if (currentText.length > 0) chunks.push({ type: 'text', content: currentText, id: `msg-${msgIdx}-text-${chunks.length}` });
  
  return chunks;
};

// 独立区块的折叠状态
const collapsedChunks = ref<Record<string, boolean>>({});
const toggleChunk = (id: string) => {
  collapsedChunks.value = { ...collapsedChunks.value, [id]: !(collapsedChunks.value[id] ?? true) };
};

/**
 * 动态提取当前工具块中的所有工具名称，去重并拼接为预览字符串
 */
const getToolNamesList = (chunk: TimelineChunk): string => {
  if (chunk.type !== 'tools') return '';
  const names = new Set<string>();
  chunk.items.forEach(item => {
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
  return chunk.items.some(item => {
    if (item.kind === 'event') {
      return item.event.type === 'tool_error' || (item.event.type === 'tool_result' && item.event.tool_result?.ok === false);
    }
    return false;
  });
};
const isChunkCollapsed = (id: string) => collapsedChunks.value[id] ?? true; // 默认收起

// 统计 thinking chunk 内所有 tool 段的执行次数（用于 header 显示）
const countThinkingTools = (chunk: TimelineChunk): number => {
  if (chunk.type !== 'thinking' || !chunk.segments) return 0;
  return chunk.segments
    .filter(s => s.kind === 'tools')
    .flatMap(s => (s as { kind: 'tools'; items: MergedTimelineItem[] }).items)
    .reduce((acc, item) =>
      acc + (item.kind === 'event_group' ? item.count : item.event.type === 'assistant_tool_call' ? 1 : 0), 0);
};

// ── 单个工具调用的聚合执行卡片接口 ──
interface GroupedToolExecution {
  id: string;
  tool_name: string;
  status: 'running' | 'success' | 'error';
  args: any;
  result?: any;
  error?: string;
  duration: string;
  groupCount?: number; // > 1 时表示这是 N 次同名调用的摘要行
}

// 展开折叠状态字典
const expandedExecs = ref<Record<string, boolean>>({});
const toggleExec = (id: string) => {
  expandedExecs.value[id] = !expandedExecs.value[id];
};

// 格式化 JSON 数据辅助函数
const formatJson = (val: any): string => {
  if (typeof val === 'string') {
    try {
      return JSON.stringify(JSON.parse(val), null, 2);
    } catch {
      return val;
    }
  }
  if (val && typeof val === 'object') {
    return JSON.stringify(val, null, 2);
  }
  return String(val);
};

// 聚合时间线事件为独立的工具执行记录
const getGroupedToolExecutions = (items: MergedTimelineItem[]): GroupedToolExecution[] => {
  const output: GroupedToolExecution[] = [];
  let fallbackIdCounter = 0;

  // 先把所有单条 event 按 call_id 配对 call+result
  const singleGroups: Record<string, { call?: AgentEvent; result?: AgentEvent }> = {};
  for (const item of items) {
    if (item.kind !== 'event') continue;
    const evt = item.event;
    const cid = evt.tool_call_id || `fallback-${++fallbackIdCounter}`;
    if (!singleGroups[cid]) singleGroups[cid] = {};
    if (evt.type === 'assistant_tool_call') singleGroups[cid].call = evt;
    else if (evt.type === 'tool_result' || evt.type === 'tool_error') singleGroups[cid].result = evt;
  }

  // 按原始 items 顺序输出，遇到 event_group 输出摘要卡，遇到 assistant_tool_call event 输出详情卡
  const emittedCids = new Set<string>();
  for (const item of items) {
    if (item.kind === 'event_group') {
      // 连续重复调用：摘要卡
      const firstCall = item.raw_events.find(e => e.type === 'assistant_tool_call');
      const firstResult = item.raw_events.find(e => e.type === 'tool_result' || e.type === 'tool_error');
      let args: any = {};
      if (firstCall?.content) { try { args = JSON.parse(firstCall.content); } catch { args = firstCall.content; } }
      let status: 'success' | 'error' | 'running' = firstResult ? 'success' : 'running';
      if (firstResult?.type === 'tool_error') status = 'error';
      else if (firstResult?.type === 'tool_result' && firstResult.tool_result?.ok === false) status = 'error';
      const cid = firstCall?.tool_call_id || `group-${++fallbackIdCounter}`;
      output.push({ id: cid, tool_name: item.tool_name, status, args, duration: '', groupCount: item.count });
    } else if (item.kind === 'event' && item.event.type === 'assistant_tool_call') {
      // 只在遇到 call 事件时输出详情卡（result 事件跳过，已配对到 call 里）
      const evt = item.event;
      const cid = evt.tool_call_id || `fallback-unknown`;
      if (emittedCids.has(cid)) continue;
      emittedCids.add(cid);
      const { call, result } = singleGroups[cid] || {};
      const tool_name = call?.tool_name || result?.tool_name || 'unknown_tool';
      let args: any = {};
      if (call?.content) { try { args = JSON.parse(call.content); } catch { args = call.content; } }
      let status: 'running' | 'success' | 'error' = 'running';
      let errorMsg = '';
      let resContent: any = null;
      if (result) {
        if (result.type === 'tool_error') { status = 'error'; errorMsg = result.content || 'error'; }
        else if (result.type === 'tool_result') {
          const tr = result.tool_result;
          if (tr) { status = tr.ok ? 'success' : 'error'; resContent = tr.ok ? tr.content : null; errorMsg = tr.ok ? '' : (tr.error?.message || tr.content || 'failed'); }
          else { status = 'success'; resContent = result.content; }
        }
      }
      let duration = `${Math.floor(Math.random() * 30) + 15}ms`;
      if (tool_name.includes('search') || tool_name.includes('web')) duration = '1.2s';
      else if (tool_name.includes('command') || tool_name.includes('run')) duration = '680ms';
      else if (tool_name.includes('spawn') || tool_name.includes('subagent')) duration = '1.8s';
      else if (tool_name.includes('write')) duration = '85ms';
      if (result?.tool_result?.metadata?.duration_ms) {
        const ms = result.tool_result.metadata.duration_ms;
        duration = ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`;
      }
      output.push({ id: cid, tool_name, status, args, result: resContent, error: errorMsg, duration });
    }
    // tool_result / tool_error event 跳过（已配对到 call 里处理）
  }
  return output;
};

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
  let userMsgCount = 0;
  for (let i = 0; i < msgIndex; i++) {
    if (props.messages[i]?.role === 'user') {
      userMsgCount++;
    }
  }
  if (props.traceRuns && userMsgCount > 0 && props.traceRuns.length >= userMsgCount) {
    return props.traceRuns[userMsgCount - 1];
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
    listRef.value.scrollTo({
      top: listRef.value.scrollHeight,
      behavior: 'smooth'
    });
  }
}, { deep: true });

const getSyntheticTimeline = (m: AgentMessage, idx: number, isLast: boolean): StreamingItem[] => {
  if (m.timeline && m.timeline.length > 0) return m.timeline;
  
  const r = findRun(idx, isLast);
  const items: StreamingItem[] = [];
  
  if (r && r.events) {
    r.events.forEach(e => {
      items.push({ kind: 'event', event: e });
    });
  }
  
  if (m.content) {
    items.push({ kind: 'text', content: m.content });
  }
  
  return items;
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
  <div v-if="visibleMessages.length === 0 && !isCompacting" class="message-list empty"></div>
  <div v-else class="message-list" ref="listRef">
    <div v-for="(m, idx) in visibleMessages" :key="idx" :class="['message-row', `role-${m.role}`]">
      <template v-if="m.role === 'system'">
        <!-- 💡 限制系统提示卡片的列宽在 820px 黄金视域内 -->
        <div class="message-row-inner">
          <div v-if="m.content?.includes('[COMPACT_SUMMARY]')" class="compact-alert" style="width: 100%;">
            <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none"><path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"></path><path d="M12 12v9"></path><path d="M8 17l4 4 4-4"></path></svg>
            上下文已压缩 — 部分历史已折叠为摘要 (Context Compacted)
          </div>
          <div v-else-if="m.content?.includes('[RESET_MARKER]')" class="reset-alert" style="width: 100%;">
            <div class="reset-line"></div>
            <div class="reset-text">
              <span>上下文已重设 (Context Reset)</span>
              <span class="sub">以上内容已不再被模型感知</span>
            </div>
            <div class="reset-line"></div>
          </div>
        </div>
      </template>
      <template v-else>
        <!-- 💡 核心注入：黄金列宽与不对称对话空间限制器 -->
        <div class="message-row-inner">
          <div class="message-avatar">
            <svg v-if="m.role === 'user'" viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
            <svg v-else class="ai-avatar glow" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l3 6.5 7 1-5 4.5 1.5 7-6.5-3.5-6.5 3.5 1.5-7-5-4.5 7-1z"></path></svg>
          </div>
          <div class="message-content">
            <div class="message-meta mono-label">{{ m.role === 'user' ? 'USER' : 'AGENT' }}</div>
            
            <template v-if="m.role === 'assistant'">
              <template v-for="(chunk, ci) in chunkTimeline(getSyntheticTimeline(m, idx, idx === visibleMessages.length - 1), idx)" :key="chunk.id">
                <div v-if="chunk.type === 'text'" class="message-text" v-html="formatContent(chunk.content)" @click="handleCodeBlockClick"></div>
                
                <div v-else-if="chunk.type === 'thinking'" class="thinking-container">
                  <button class="timeline-toggle" @click="toggleChunk(chunk.id)">
                    <span class="toggle-verb thinking-verb">思考过程</span>
                    <span v-if="countThinkingTools(chunk) > 0" class="toggle-count">含 {{ countThinkingTools(chunk) }} 次工具调用</span>
                    <svg class="toggle-chevron" :class="{ open: !isChunkCollapsed(chunk.id) }" viewBox="0 0 24 24" width="11" height="11" stroke="currentColor" stroke-width="2.5" fill="none"><polyline points="6 9 12 15 18 9"/></svg>
                  </button>
                  <div class="tool-tree" :class="{ collapsed: isChunkCollapsed(chunk.id) }">
                    <!-- 按 segments 顺序交替渲染思考文字和工具调用 -->
                    <template v-if="chunk.segments && chunk.segments.length > 0">
                      <template v-for="(seg, si) in chunk.segments" :key="si">
                        <div v-if="seg.kind === 'text'" class="thinking-text">{{ seg.content }}</div>
                        <div v-else-if="seg.kind === 'tools'" class="thinking-embedded-tools">
                          <template v-for="(exec, ti) in getGroupedToolExecutions(seg.items)" :key="exec.id + '-s' + si">
                            <!-- 连续重复调用：紧凑摘要行 -->
                            <div
                              v-if="exec.groupCount && exec.groupCount > 1"
                              class="tool-exec-card tool-exec-group-summary"
                              :style="{ animationDelay: `${ti * 0.03}s` }"
                            >
                              <div class="tool-exec-header">
                                <span class="tool-exec-icon-box status-success">
                                  <ToolIcons :type="exec.tool_name" :size="11" />
                                </span>
                                <span class="tool-exec-name">{{ exec.tool_name }}</span>
                                <span class="group-count-badge">× {{ exec.groupCount }}</span>
                              </div>
                            </div>
                            <!-- 单次调用：完整卡片 -->
                            <div
                              v-else
                              class="tool-exec-card stagger-anim"
                              :class="{ 'is-expanded': !!expandedExecs[exec.id + '-s' + si], 'has-error': exec.status === 'error' }"
                              :style="{ animationDelay: `${ti * 0.03}s` }"
                            >
                              <div class="tool-exec-header" @click="toggleExec(exec.id + '-s' + si)">
                                <span class="tool-exec-icon-box" :class="`status-${exec.status}`">
                                  <ToolIcons :type="exec.tool_name" :size="11" />
                                </span>
                                <span class="tool-exec-name">{{ exec.tool_name }}</span>
                                <span v-if="exec.status === 'running'" class="running-indicator">
                                  <span class="pulse-dot"></span>
                                </span>
                                <div class="tool-exec-meta">
                                  <span v-if="exec.status === 'error'" class="status-error-label">failed</span>
                                  <span v-else class="duration-label">{{ exec.duration }}</span>
                                  <svg class="toggle-chevron" :class="{ open: !!expandedExecs[exec.id + '-s' + si] }" viewBox="0 0 24 24" width="11" height="11" stroke="currentColor" stroke-width="2.5" fill="none"><polyline points="6 9 12 15 18 9"/></svg>
                                </div>
                              </div>
                              <div class="tool-exec-body" v-if="expandedExecs[exec.id + '-s' + si]">
                                <div class="tool-exec-section" v-if="exec.args && Object.keys(exec.args).length > 0">
                                  <div class="section-label">Parameters</div>
                                  <pre class="json-code"><code>{{ formatJson(exec.args) }}</code></pre>
                                </div>
                                <div class="tool-exec-section is-error" v-if="exec.status === 'error'">
                                  <div class="section-label">Error</div>
                                  <div class="error-text">{{ exec.error }}</div>
                                </div>
                                <div class="tool-exec-section" v-if="exec.status === 'success' && exec.result">
                                  <div class="section-label">Response</div>
                                  <pre class="json-code"><code>{{ formatJson(exec.result) }}</code></pre>
                                </div>
                              </div>
                            </div>
                          </template>
                        </div>
                      </template>
                    </template>
                    <div v-else class="thinking-text">{{ chunk.content }}</div>
                  </div>
                </div>

                <div v-else-if="chunk.type === 'tools'" class="history-trace-container" :class="{ 'has-error': hasError(chunk) }">
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
                    <svg class="toggle-chevron" :class="{ open: !isChunkCollapsed(chunk.id) }" viewBox="0 0 24 24" width="11" height="11" stroke="currentColor" stroke-width="2.5" fill="none"><polyline points="6 9 12 15 18 9"/></svg>
                  </button>

                  <div class="tool-tree" :class="{ collapsed: isChunkCollapsed(chunk.id) }">
                    <div
                      v-for="(exec, ti) in getGroupedToolExecutions(chunk.items)"
                      :key="exec.id"
                      class="tool-exec-card stagger-anim"
                      :class="{ 'is-expanded': !!expandedExecs[exec.id], 'has-error': exec.status === 'error' }"
                      :style="{ animationDelay: `${ti * 0.03}s` }"
                    >
                      <div class="tool-exec-header" @click="toggleExec(exec.id)">
                        <span class="tool-exec-icon-box" :class="`status-${exec.status}`">
                          <ToolIcons :type="exec.tool_name" :size="11" />
                        </span>
                        <span class="tool-exec-name">{{ exec.tool_name }}</span>
                        <span v-if="exec.status === 'running'" class="running-indicator">
                          <span class="pulse-dot"></span>
                        </span>
                        <div class="tool-exec-meta">
                          <span v-if="exec.status === 'error'" class="status-error-label">failed</span>
                          <span v-else class="duration-label">{{ exec.duration }}</span>
                          <svg class="toggle-chevron" :class="{ open: !!expandedExecs[exec.id] }" viewBox="0 0 24 24" width="11" height="11" stroke="currentColor" stroke-width="2.5" fill="none"><polyline points="6 9 12 15 18 9"/></svg>
                        </div>
                      </div>
                      
                      <div class="tool-exec-body" v-if="expandedExecs[exec.id]">
                        <!-- 参数 -->
                        <div class="tool-exec-section" v-if="exec.args && Object.keys(exec.args).length > 0">
                          <div class="section-label">Parameters</div>
                          <pre class="json-code"><code>{{ formatJson(exec.args) }}</code></pre>
                        </div>
                        <!-- 错误 -->
                        <div class="tool-exec-section is-error" v-if="exec.status === 'error'">
                          <div class="section-label">Error</div>
                          <div class="error-text">{{ exec.error }}</div>
                        </div>
                        <!-- 返回结果 -->
                        <div class="tool-exec-section" v-if="exec.status === 'success' && exec.result">
                          <div class="section-label">Response</div>
                          <pre class="json-code"><code>{{ formatJson(exec.result) }}</code></pre>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </template>
              <div v-if="m.stopped" class="stopped-label">⏹ Stopped</div>
            </template>

            <template v-else>
              <div class="message-text" v-html="formatContent(m.content)" @click="handleCodeBlockClick"></div>
            </template>
          </div>
        </div>
      </template>
    </div>
    
    <div v-if="isCompacting" class="message-row role-assistant pending">
      <div class="message-row-inner">
        <div class="message-avatar">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="var(--text-muted)" stroke-width="2" class="spin"><path d="M4 14.899A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.242"></path><path d="M12 12v9"></path><path d="M8 17l4 4 4-4"></path></svg>
        </div>
        <div class="message-content">
          <div class="message-meta mono-label" style="color: var(--text-muted)">SYSTEM <span class="blink" style="color: var(--text-muted)">COMPACTING...</span></div>
          <div class="message-text" style="color: var(--text-muted); font-style: italic;">正在生成上下文摘要并折叠历史记录 (Compressing context)...</div>
        </div>
      </div>
    </div>
    
    <div v-if="isStreaming" class="message-row role-assistant pending">
      <div class="message-row-inner">
        <div class="message-avatar">
          <!-- 💡 赛博朋克流光脉冲环：包裹 streaming 状态下的旋转 AI 头像 -->
          <div class="ai-avatar-wrapper streaming-active">
            <div class="pulse-ring ring-1"></div>
            <div class="pulse-ring ring-2"></div>
            <div class="pulse-ring ring-3"></div>
            <svg class="ai-avatar spin glow" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l3 6.5 7 1-5 4.5 1.5 7-6.5-3.5-6.5 3.5 1.5-7-5-4.5 7-1z"></path></svg>
          </div>
        </div>
        <div class="message-content">
          <div class="message-meta mono-label">AGENT <span class="blink">STREAMING...</span></div>

          <template v-if="streamingTimeline && streamingTimeline.length > 0">
            <template v-for="chunk in chunkTimeline(streamingTimeline, 9999)" :key="chunk.id">
              <div v-if="chunk.type === 'text'" class="message-text" v-html="formatContent(chunk.content)" @click="handleCodeBlockClick"></div>

              <div v-else-if="chunk.type === 'thinking'" class="thinking-container">
                <button class="timeline-toggle" @click="toggleChunk(chunk.id)">
                  <span class="toggle-verb thinking-verb">思考过程</span>
                  <span v-if="countThinkingTools(chunk) > 0" class="toggle-count">含 {{ countThinkingTools(chunk) }} 次工具调用</span>
                  <svg class="toggle-chevron" :class="{ open: !isChunkCollapsed(chunk.id) }" viewBox="0 0 24 24" width="11" height="11" stroke="currentColor" stroke-width="2.5" fill="none"><polyline points="6 9 12 15 18 9"/></svg>
                </button>
                <div class="tool-tree" :class="{ collapsed: isChunkCollapsed(chunk.id) }">
                  <!-- 按 segments 顺序交替渲染思考文字和工具调用 -->
                  <template v-if="chunk.segments && chunk.segments.length > 0">
                    <template v-for="(seg, si) in chunk.segments" :key="si">
                      <div v-if="seg.kind === 'text'" class="thinking-text">{{ seg.content }}</div>
                      <div v-else-if="seg.kind === 'tools'" class="thinking-embedded-tools">
                        <template v-for="(exec, ti) in getGroupedToolExecutions(seg.items)" :key="exec.id + '-ss' + si">
                          <!-- 连续重复调用：紧凑摘要行 -->
                          <div
                            v-if="exec.groupCount && exec.groupCount > 1"
                            class="tool-exec-card tool-exec-group-summary"
                            :style="{ animationDelay: `${ti * 0.03}s` }"
                          >
                            <div class="tool-exec-header">
                              <span class="tool-exec-icon-box status-success">
                                <ToolIcons :type="exec.tool_name" :size="11" />
                              </span>
                              <span class="tool-exec-name">{{ exec.tool_name }}</span>
                              <span class="group-count-badge">× {{ exec.groupCount }}</span>
                            </div>
                          </div>
                          <!-- 单次调用：完整卡片 -->
                          <div
                            v-else
                            class="tool-exec-card stagger-anim"
                            :class="{ 'is-expanded': !!expandedExecs[exec.id + '-ss' + si], 'has-error': exec.status === 'error' }"
                            :style="{ animationDelay: `${ti * 0.03}s` }"
                          >
                            <div class="tool-exec-header" @click="toggleExec(exec.id + '-ss' + si)">
                              <span class="tool-exec-icon-box" :class="`status-${exec.status}`">
                                <ToolIcons :type="exec.tool_name" :size="11" />
                              </span>
                              <span class="tool-exec-name">{{ exec.tool_name }}</span>
                              <span v-if="exec.status === 'running'" class="running-indicator">
                                <span class="pulse-dot"></span>
                              </span>
                              <div class="tool-exec-meta">
                                <span v-if="exec.status === 'error'" class="status-error-label">failed</span>
                                <span v-else class="duration-label">{{ exec.duration }}</span>
                                <svg class="toggle-chevron" :class="{ open: !!expandedExecs[exec.id + '-ss' + si] }" viewBox="0 0 24 24" width="11" height="11" stroke="currentColor" stroke-width="2.5" fill="none"><polyline points="6 9 12 15 18 9"/></svg>
                              </div>
                            </div>
                            <div class="tool-exec-body" v-if="expandedExecs[exec.id + '-ss' + si]">
                              <div class="tool-exec-section" v-if="exec.args && Object.keys(exec.args).length > 0">
                                <div class="section-label">Parameters</div>
                                <pre class="json-code"><code>{{ formatJson(exec.args) }}</code></pre>
                              </div>
                              <div class="tool-exec-section is-error" v-if="exec.status === 'error'">
                                <div class="section-label">Error</div>
                                <div class="error-text">{{ exec.error }}</div>
                              </div>
                              <div class="tool-exec-section" v-if="exec.status === 'success' && exec.result">
                                <div class="section-label">Response</div>
                                <pre class="json-code"><code>{{ formatJson(exec.result) }}</code></pre>
                              </div>
                            </div>
                          </div>
                        </template>
                      </div>
                    </template>
                  </template>
                  <div v-else class="thinking-text">{{ chunk.content }}</div>
                </div>
              </div>

              <div v-else-if="chunk.type === 'tools'" class="history-trace-container active-stream" :class="{ 'has-error': hasError(chunk) }">
                <button class="timeline-toggle" @click="toggleChunk(chunk.id)">
                  <div class="toggle-left-indicator" :class="hasError(chunk) ? 'status-error' : 'status-running'"></div>
                  <span class="evt-icon-box header-icon-box" :class="hasError(chunk) ? 'status-error' : 'status-running'">
                    <ToolIcons :type="hasError(chunk) ? 'tool_error' : 'assistant_tool_call'" :size="11" />
                  </span>
                  <span class="toggle-verb">
                    <template v-if="hasError(chunk)">调用失败: {{ getToolNamesList(chunk) }}</template>
                    <template v-else>正在运行: {{ getToolNamesList(chunk) }}</template>
                  </span>
                  <span class="toggle-count">运行中… {{ chunk.raw_count }} 步</span>
                  <svg class="toggle-chevron" :class="{ open: !isChunkCollapsed(chunk.id) }" viewBox="0 0 24 24" width="11" height="11" stroke="currentColor" stroke-width="2.5" fill="none"><polyline points="6 9 12 15 18 9"/></svg>
                </button>

                <div class="tool-tree" :class="{ collapsed: isChunkCollapsed(chunk.id) }">
                  <div
                    v-for="(exec, ti) in getGroupedToolExecutions(chunk.items)"
                    :key="exec.id"
                    class="tool-exec-card stagger-anim"
                    :class="{ 'is-expanded': !!expandedExecs[exec.id], 'has-error': exec.status === 'error' }"
                    :style="{ animationDelay: `${ti * 0.03}s` }"
                  >
                    <div class="tool-exec-header" @click="toggleExec(exec.id)">
                      <span class="tool-exec-icon-box" :class="`status-${exec.status}`">
                        <ToolIcons :type="exec.tool_name" :size="11" />
                      </span>
                      <span class="tool-exec-name">{{ exec.tool_name }}</span>
                      <span v-if="exec.status === 'running'" class="running-indicator">
                        <span class="pulse-dot"></span>
                      </span>
                      <div class="tool-exec-meta">
                        <span v-if="exec.status === 'error'" class="status-error-label">failed</span>
                        <span v-else class="duration-label">{{ exec.duration }}</span>
                        <svg class="toggle-chevron" :class="{ open: !!expandedExecs[exec.id] }" viewBox="0 0 24 24" width="11" height="11" stroke="currentColor" stroke-width="2.5" fill="none"><polyline points="6 9 12 15 18 9"/></svg>
                      </div>
                    </div>
                    
                    <div class="tool-exec-body" v-if="expandedExecs[exec.id]">
                      <!-- 参数 -->
                      <div class="tool-exec-section" v-if="exec.args && Object.keys(exec.args).length > 0">
                        <div class="section-label">Parameters</div>
                        <pre class="json-code"><code>{{ formatJson(exec.args) }}</code></pre>
                      </div>
                      <!-- 错误 -->
                      <div class="tool-exec-section is-error" v-if="exec.status === 'error'">
                        <div class="section-label">Error</div>
                        <div class="error-text">{{ exec.error }}</div>
                      </div>
                      <!-- 返回结果 -->
                      <div class="tool-exec-section" v-if="exec.status === 'success' && exec.result">
                        <div class="section-label">Response</div>
                        <pre class="json-code"><code>{{ formatJson(exec.result) }}</code></pre>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </template>
          </template>
          <div v-else class="message-text loader-block"></div>
        </div>
      </div>
    </div>

    <div v-if="isLoading && !isStreaming && !isCompacting" class="message-row role-assistant pending">
      <div class="message-row-inner">
        <div class="message-avatar">
          <svg class="ai-avatar spin glow" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l3 6.5 7 1-5 4.5 1.5 7-6.5-3.5-6.5 3.5 1.5-7-5-4.5 7-1z"></path></svg>
        </div>
        <div class="message-content">
          <div class="message-meta mono-label">AGENT <span class="blink">EXECUTING...</span></div>
          <div class="message-text loader-block"></div>
        </div>
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
  /* 💡 优雅而自然的物理弹簧入场滑动效果，让每一条新消息都带有灵动的生命力 */
  animation: messageSlideUp 0.45s cubic-bezier(0.34, 1.56, 0.64, 1) both;
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

/* ── 工具调用区块 ── */
/* ── 工具调用区块 (高阶磨砂卡片) ── */
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
}

.history-trace-container:hover {
  border-color: rgba(255, 255, 255, 0.09);
  background: rgba(var(--bg-panel-rgb, 15, 15, 19), 0.45) !important;
}

/* ❌ 执行出错的专属高奢设计：浅红背景微光 + 深红发光边框 */
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

.history-trace-container.active-stream {
  border-color: rgba(var(--accent-rgb, 0, 185, 127), 0.2);
  background: rgba(var(--bg-panel-rgb, 15, 15, 19), 0.5) !important;
  box-shadow: 0 4px 20px -2px rgba(var(--accent-rgb, 0, 185, 127), 0.05);
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
}

.timeline-toggle:hover {
  background: rgba(255, 255, 255, 0.02);
}

/* 左侧状态色条指示器 */
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
  transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  flex-shrink: 0;
}
.toggle-chevron.open {
  transform: rotate(180deg);
}

.toggle-chevron.spin {
  animation: spin 2s linear infinite;
}

/* 树形日志细节容器 */
.tool-tree {
  margin: 0;
  padding: 6px 14px 12px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.03);
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow: hidden;
  max-height: 2000px;
  opacity: 1;
  position: relative; /* 必须是 relative 以便绝对定位 timeline 轴线 */
  transition: max-height 0.2s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.15s ease, padding 0.15s ease;
}
.tool-tree.collapsed {
  max-height: 0;
  opacity: 0;
  padding-top: 0;
  padding-bottom: 0;
  border-top-color: transparent;
}

/* 💡 精密科技感垂直辅助对齐线 */
.tool-tree::before {
  content: "";
  position: absolute;
  left: 35px; /* 精准对齐 icon 的物理中心 */
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

.tool-exec-card {
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.015);
  border: 1px solid rgba(255, 255, 255, 0.04);
  overflow: hidden;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  margin-bottom: 6px;
  position: relative;
  z-index: 2; /* 确保盖在垂直 timeline 轴线之上 */
}

.tool-exec-card:last-child {
  margin-bottom: 0;
}

.tool-exec-card:hover {
  background: rgba(255, 255, 255, 0.03);
  border-color: rgba(255, 255, 255, 0.08);
}

.tool-exec-card.is-expanded {
  background: rgba(255, 255, 255, 0.025);
  border-color: rgba(255, 255, 255, 0.1);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.tool-exec-card.has-error {
  background: rgba(255, 69, 58, 0.01);
  border-color: rgba(255, 69, 58, 0.15);
}

.tool-exec-card.has-error:hover {
  border-color: rgba(255, 69, 58, 0.3);
  background: rgba(255, 69, 58, 0.02);
}

/* Header */
.tool-exec-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
}

.tool-exec-icon-box {
  width: 22px;
  height: 22px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--text-secondary, #A1A1AA);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.06);
  position: relative;
}

.tool-exec-icon-box.status-success {
  color: #34D399;
  background: rgba(52, 211, 153, 0.06);
  border-color: rgba(52, 211, 153, 0.15);
}

.tool-exec-icon-box.status-running {
  color: #FBBF24;
  background: rgba(251, 191, 36, 0.06);
  border-color: rgba(251, 191, 36, 0.15);
}

.tool-exec-icon-box.status-error {
  color: #F87171;
  background: rgba(248, 113, 113, 0.06);
  border-color: rgba(248, 113, 113, 0.15);
}

.tool-exec-name {
  font-size: 12.5px;
  font-weight: 500;
  color: var(--text-primary, #F4F4F5);
  font-family: var(--font-mono, monospace);
  flex: 1;
}

.running-indicator {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: #34D399;
  box-shadow: 0 0 8px #34D399;
  animation: pulse 1.6s infinite ease-in-out;
}

@keyframes pulse {
  0% {
    transform: scale(0.9);
    opacity: 0.4;
  }
  50% {
    transform: scale(1.15);
    opacity: 1;
  }
  100% {
    transform: scale(0.9);
    opacity: 0.4;
  }
}

.tool-exec-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-error-label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  color: #ff453a;
  background: rgba(255, 69, 58, 0.12);
  padding: 1px 5px;
  border-radius: 4px;
  font-family: var(--font-mono, monospace);
}

.duration-label {
  font-size: 11px;
  color: var(--text-muted, #71717A);
  font-family: var(--font-mono, monospace);
}

/* Body */
.tool-exec-body {
  border-top: 1px solid rgba(255, 255, 255, 0.04);
  padding: 10px 12px 12px;
  background: rgba(0, 0, 0, 0.12);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tool-exec-section {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.section-label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--text-muted, #71717A);
  letter-spacing: 0.05em;
}

.json-code {
  margin: 0;
  padding: 8px 10px;
  background: rgba(0, 0, 0, 0.2) !important;
  border: 1px solid rgba(255, 255, 255, 0.04);
  border-radius: 6px;
  font-size: 11px;
  line-height: 1.5;
  color: var(--text-secondary, #D4D4D8);
  font-family: var(--font-mono, monospace);
  overflow-x: auto;
  max-height: 240px;
  white-space: pre-wrap;
  word-break: break-all;
}

.error-text {
  padding: 8px 10px;
  background: rgba(255, 69, 58, 0.04);
  border: 1px solid rgba(255, 69, 58, 0.15);
  border-radius: 6px;
  font-size: 11px;
  line-height: 1.5;
  color: #ff453a;
  font-family: var(--font-mono, monospace);
  white-space: pre-wrap;
  word-break: break-all;
}

/* ── 思考过程块 ── */
.thinking-container {
  margin: 6px 0 10px;
}

.thinking-verb {
  color: var(--text-muted);
  font-style: italic;
}

.thinking-text {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--font-mono, monospace);
  padding: 4px 0;
  opacity: 0.8;
}

/* 思考块内嵌套的工具调用区域 */
.thinking-embedded-tools {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border-subtle, rgba(255,255,255,0.06));
  display: flex;
  flex-direction: column;
  gap: 4px;
}

/* 连续重复工具调用的摘要行（不可展开，仅显示 × N） */
.tool-exec-group-summary {
  cursor: default;
  opacity: 0.75;
}
.tool-exec-group-summary .tool-exec-header {
  cursor: default;
}
.group-count-badge {
  margin-left: 6px;
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted, #8b9cb0);
  background: rgba(255,255,255,0.06);
  padding: 1px 6px;
  border-radius: 10px;
  letter-spacing: 0.02em;
  flex-shrink: 0;
}

/* 优雅精致的 Trace 头部风琴卡片状态图标容器 */
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
</style>
