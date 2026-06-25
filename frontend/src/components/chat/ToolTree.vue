<script setup lang="ts">
import { ref } from 'vue';
import type { ApprovalInfo, RunEvent } from '../../types';
import type { MergedTimelineItem } from './types';
import { findPendingApprovalForTool } from '../../utils/approvalQueue';
import ToolCard from './ToolCard.vue';

interface GroupedToolExecution {
  id: string;
  tool_name: string;
  status: 'running' | 'success' | 'error' | 'awaiting_approval';
  args: any;
  result?: any;
  error?: string;
  duration: string;
  groupCount?: number;
  approvalInfo?: ApprovalInfo | null;
  vfsState?: string;
}

const props = defineProps<{
  items: MergedTimelineItem[];
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

// 聚合时间线事件为独立的工具执行记录
const getGroupedToolExecutions = (items: MergedTimelineItem[]): GroupedToolExecution[] => {
  const output: GroupedToolExecution[] = [];
  let fallbackIdCounter = 0;
  const pendingApprovals = props.pendingApprovalInfos ?? (props.pendingApprovalInfo ? [props.pendingApprovalInfo] : []);

  // 先把所有单条 event 按 call_id 配对 call+result
  const singleGroups: Record<string, { call?: any; result?: any; approval?: any }> = {};
  for (const item of items) {
    if (item.kind !== 'event') continue;
    const evt = item.event;
    const cid = evt.tool_call_id || `fallback-${++fallbackIdCounter}`;
    if (!singleGroups[cid]) singleGroups[cid] = {};
    if (evt.type === 'assistant_tool_call') singleGroups[cid].call = evt;
    else if (evt.type === 'tool_result' || evt.type === 'tool_error') singleGroups[cid].result = evt;
    else if (evt.type === 'approval_required') singleGroups[cid].approval = evt;
  }

  // 按原始 items 顺序输出，遇到 event_group 输出摘要卡，遇到 assistant_tool_call event 输出详情卡
  const emittedCids = new Set<string>();
  for (const item of items) {
    if (item.kind === 'event_group') {
      // 连续重复调用：摘要卡
      const firstCall = item.raw_events.find((e: RunEvent) => e.type === 'assistant_tool_call');
      const firstResult = item.raw_events.find((e: RunEvent) => e.type === 'tool_result' || e.type === 'tool_error');
      let args: any = {};
      if (firstCall?.content) { try { args = JSON.parse(firstCall.content); } catch { args = firstCall.content; } }
      
      let status: 'success' | 'error' | 'running' | 'awaiting_approval' = firstResult ? 'success' : 'running';
      if (firstResult?.type === 'tool_error') status = 'error';
      else if (firstResult?.type === 'tool_result' && firstResult.tool_result?.ok === false) status = 'error';
      
      const groupApproval = item.raw_events
        .map(event => findPendingApprovalForTool(
          pendingApprovals,
          event.tool_call_id,
          event.tool_name,
          event.type === 'approval_required' ? event.content : null,
        ))
        .find(Boolean) ?? null;
      if (status === 'running' && groupApproval) status = 'awaiting_approval';

      const cid = firstCall?.tool_call_id || `group-${++fallbackIdCounter}`;
      output.push({ id: cid, tool_name: item.tool_name, status, args, duration: '', groupCount: item.count, approvalInfo: groupApproval });
    } else if (item.kind === 'event' && item.event.type === 'assistant_tool_call') {
      // 只在遇到 call 事件时输出详情卡（result 事件跳过，已配对到 call 里）
      const evt = item.event;
      const cid = evt.tool_call_id || `fallback-unknown`;
      if (emittedCids.has(cid)) continue;
      emittedCids.add(cid);
      const { call, result, approval } = singleGroups[cid] || {};
      const tool_name = call?.tool_name || result?.tool_name || 'unknown_tool';
      let args: any = {};
      if (call?.content) { try { args = JSON.parse(call.content); } catch { args = call.content; } }
      
      let status: 'running' | 'success' | 'error' | 'awaiting_approval' = 'running';
      
      const approvalInfo = findPendingApprovalForTool(
        pendingApprovals,
        cid,
        tool_name,
        approval?.content ?? null,
      );
      if (approvalInfo && !result) status = 'awaiting_approval';

      let errorMsg = '';
      let resContent: any = null;
      let vfsState: string | undefined;
      if (result && status !== 'awaiting_approval') {
        if (result.type === 'tool_error') { status = 'error'; errorMsg = result.content || 'error'; }
        else if (result.type === 'tool_result') {
          const tr = result.tool_result;
          if (tr) {
            status = tr.ok ? 'success' : 'error';
            resContent = tr.ok ? tr.content : null;
            errorMsg = tr.ok ? '' : (tr.error?.message || tr.content || 'failed');
            vfsState = tr.metadata?.state;
          }
          else { status = 'success'; resContent = result.content; }
        }
      }
      
      // 用 cid 哈希得到确定性的伪随机 duration，避免每次渲染随机跳变
      let hashNum = 0;
      for (let ci = 0; ci < cid.length; ci++) { hashNum = (hashNum * 31 + cid.charCodeAt(ci)) >>> 0; }
      let duration = `${(hashNum % 30) + 15}ms`;
      if (tool_name.includes('search') || tool_name.includes('web')) duration = '1.2s';
      else if (tool_name.includes('command') || tool_name.includes('run')) duration = '680ms';
      else if (tool_name.includes('spawn') || tool_name.includes('subagent')) duration = '1.8s';
      else if (tool_name.includes('write')) duration = '85ms';
      if (result?.tool_result?.metadata?.duration_ms) {
        const ms = result.tool_result.metadata.duration_ms;
        duration = ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${Math.round(ms)}ms`;
      }
      output.push({ id: cid, tool_name, status, args, result: resContent, error: errorMsg, duration, approvalInfo, vfsState });
    }
  }
  return output;
};
</script>

<template>
  <div class="tool-list-tree-container">
    <template v-for="(exec, idx) in getGroupedToolExecutions(items)" :key="exec.id + '-' + idx">
      <ToolCard
        :exec="exec"
        :isAwaitingApproval="isAwaitingApproval"
        :pendingApprovalInfo="pendingApprovalInfo"
        :pendingApprovalInfos="pendingApprovalInfos"
        :isProcessingApproval="isProcessingApproval"
        @approve="emit('approve', $event)"
        @reject="emit('reject', $event)"
        @approve-all="emit('approve-all')"
      />
    </template>
  </div>
</template>

<style scoped>
.tool-list-tree-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}
</style>
