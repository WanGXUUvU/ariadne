import { ref, type Ref } from 'vue';

import { api } from '../../api/client';
import type { AgentMessage, ApprovalInfo, StreamingItem, TraceRunSummary } from '../../types';
import { removePendingApproval, upsertPendingApproval } from '../../utils/approvalQueue';
import { reconstructUiMessages, writeTimelineToStore } from './helpers';

interface ApprovalFlowOptions {
  sessions: Ref<any[]>;
  activeSessionId: Ref<string | null>;
  currentMessages: Ref<AgentMessage[]>;
  traceRuns: Ref<TraceRunSummary[]>;
  isStreaming: Ref<boolean>;
  isChatLoading: Ref<boolean>;
  streamingTimeline: Ref<StreamingItem[]>;
  streamingPrefixTimeline: Ref<StreamingItem[]>;
  lastCompletedRun: Ref<TraceRunSummary | null>;
  errorMsg: Ref<string | null>;
  isAwaitingApproval: Ref<boolean>;
  pendingApprovalInfo: Ref<ApprovalInfo | null>;
  pendingApprovalInfos: Ref<ApprovalInfo[]>;
  isResolvingApproval: Ref<boolean>;
  onLiveRunEvent: (sessionId: string, ev: any) => void;
  extractChildAgents: (sessionId: string, msgs: AgentMessage[], traceRuns: TraceRunSummary[]) => void;
  updatePermissionProfile: (profile: string) => Promise<void>;
}

export function useApprovalFlow(options: ApprovalFlowOptions) {
  const {
    sessions,
    activeSessionId,
    currentMessages,
    traceRuns,
    isStreaming,
    isChatLoading,
    streamingTimeline,
    streamingPrefixTimeline,
    lastCompletedRun,
    errorMsg,
    isAwaitingApproval,
    pendingApprovalInfo,
    pendingApprovalInfos,
    isResolvingApproval,
    onLiveRunEvent,
    extractChildAgents,
    updatePermissionProfile,
  } = options;

  const syncApprovalHead = () => {
    pendingApprovalInfo.value = pendingApprovalInfos.value[0] ?? null;
    isAwaitingApproval.value = pendingApprovalInfos.value.length > 0;
  };

  async function handleApprovalStream(streamFn: () => AsyncGenerator<any>, approvalId?: string) {
    const targetApprovalId = approvalId ?? pendingApprovalInfo.value?.approval_id;
    if (!targetApprovalId) return;

    // ── Step 1：收集上一条 assistant 消息的 timeline（作为流式前缀，保持上下文连续性）──
    const initialTimeline: StreamingItem[] = [];
    for (let i = currentMessages.value.length - 1; i >= 0; i--) {
      const message = currentMessages.value[i];
      if (message.role === 'assistant' && message.timeline && message.timeline.length > 0) {
        initialTimeline.push(...message.timeline);
        break;
      }
    }

    // ── Step 2：只移除当前审批卡，保留同批剩余待审批卡 ──
    pendingApprovalInfos.value = removePendingApproval(pendingApprovalInfos.value, targetApprovalId);
    syncApprovalHead();

    // ── Step 3：移除 content:null 的占位消息（由 paused 插入的空壳），避免与新流式块重叠 ──
    //   有真实 content 的消息保留（它们是有价值的历史上下文）
    currentMessages.value = currentMessages.value.filter(
      m => !(m.role === 'assistant' && m.content === null)
    );

    // ── Step 3b：清除保留消息的 timeline（tool cards 已并入 streamingTimeline 前缀，避免重复渲染）──
    //   流结束后 reconstructUiMessages 会从服务器重建最终完整状态
    currentMessages.value = currentMessages.value.map(m => {
      if (m.role === 'assistant' && m.timeline && m.timeline.length > 0) {
        return { ...m, timeline: [] };
      }
      return m;
    });

    isStreaming.value = true;
    isChatLoading.value = true;
    isResolvingApproval.value = true;
    // ── Step 4：设置流式块前缀（initialTimeline），让 call+result 能正确配对显示 ──
    // streaming block 会渲染 streamingPrefixTimeline + streamingTimeline
    streamingPrefixTimeline.value = [...initialTimeline];
    streamingTimeline.value = [];
    errorMsg.value = null;
    let capturedRunId: string | null = null;
    let stillAwaitingApproval = false;

    try {
      for await (const frame of streamFn()) {
        if (frame.type === 'start' || frame.type === 'resume') {
          capturedRunId = frame.data.run_id;
        } else if (frame.type === 'delta') {
          const tl = streamingTimeline.value;
          const last = tl[tl.length - 1];
          if (last?.kind === 'text') {
            last.content += frame.data.content;
            streamingTimeline.value = [...tl];
          } else {
            streamingTimeline.value = [...tl, { kind: 'text', content: frame.data.content }];
          }
        } else if (frame.type === 'thinking_delta') {
          const tl = streamingTimeline.value;
          const last = tl[tl.length - 1];
          if (last?.kind === 'thinking') {
            last.content += frame.data.content;
            streamingTimeline.value = [...tl];
          } else {
            streamingTimeline.value = [...tl, { kind: 'thinking', content: frame.data.content }];
          }
        } else if (frame.type === 'run_event') {
          if (frame.data.type !== 'final_answer') {
            streamingTimeline.value = [...streamingTimeline.value, { kind: 'event', event: frame.data }];
          }
          if (activeSessionId.value) {
            onLiveRunEvent(activeSessionId.value, frame.data);
          }
        } else if (frame.type === 'paused') {
          stillAwaitingApproval = true;
          isAwaitingApproval.value = true;
          isResolvingApproval.value = false;

          const partialTimeline = [...initialTimeline, ...streamingTimeline.value];
          if (capturedRunId) {
            writeTimelineToStore(capturedRunId, partialTimeline);
          }

          if (partialTimeline.length > 0) {
            const newMsgs = [...currentMessages.value];
            let found = false;
            for (let i = newMsgs.length - 1; i >= 0; i--) {
              if (newMsgs[i].role === 'assistant') {
                newMsgs[i] = { ...newMsgs[i], timeline: partialTimeline };
                found = true;
                break;
              }
            }
            if (!found) {
              newMsgs.push({ role: 'assistant', content: null, timeline: partialTimeline });
            }
            currentMessages.value = newMsgs;
          }

          const nextApprovalId = frame.data.approval_id;
          if (nextApprovalId) {
            const pendingApproval = {
              approval_id: nextApprovalId,
              tool_name: '',
              arguments: '',
              run_id: capturedRunId ?? '',
            };
            pendingApprovalInfos.value = upsertPendingApproval(pendingApprovalInfos.value, pendingApproval);
            syncApprovalHead();

            api.getApproval(nextApprovalId).then(info => {
              pendingApprovalInfos.value = upsertPendingApproval(pendingApprovalInfos.value, {
                approval_id: nextApprovalId,
                tool_name: info.tool_name,
                arguments: info.arguments,
                run_id: capturedRunId ?? '',
                tool_call_id: (info as any).tool_call_id ?? undefined,
              });
              syncApprovalHead();
            }).catch(() => {});
          }
        } else if (frame.type === 'end') {
          const frozenTimeline = [...initialTimeline, ...streamingTimeline.value];
          if (capturedRunId) {
            writeTimelineToStore(capturedRunId, frozenTimeline);
          }

          if (activeSessionId.value) {
            const [, traceResult] = await Promise.allSettled([
              api.getSessions().then(data => { sessions.value = data || []; }),
              api.getTrace(activeSessionId.value),
            ]);
            if (traceResult.status === 'fulfilled') {
              traceRuns.value = (traceResult.value as any).runs || [];
            }
            const activeMsgs = frame.data.state?.messages || [];
            currentMessages.value = reconstructUiMessages(traceRuns.value, activeMsgs);
            extractChildAgents(activeSessionId.value, currentMessages.value, traceRuns.value);
            if (capturedRunId) {
              lastCompletedRun.value = traceRuns.value.find(r => r.run_id === capturedRunId) ?? null;
            }
          }
        } else if (frame.type === 'error') {
          errorMsg.value = frame.data.message ?? 'Approval error';
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        errorMsg.value = 'Resume failed: ' + err.message;
      }
    } finally {
      isResolvingApproval.value = false;
      isAwaitingApproval.value = stillAwaitingApproval || pendingApprovalInfos.value.length > 0;
      pendingApprovalInfo.value = pendingApprovalInfos.value[0] ?? null;
      isStreaming.value = false;
      isChatLoading.value = false;
      streamingTimeline.value = [];
      streamingPrefixTimeline.value = []; // 清空前缀，流式块消失后不留残影
    }
  }

  const approveAction = async (approvalId?: string) => {
    const id = approvalId ?? pendingApprovalInfo.value?.approval_id;
    if (!id) return;
    await handleApprovalStream(() => api.streamApprove(id), id);
  };

  const rejectAction = async (approvalId?: string) => {
    const id = approvalId ?? pendingApprovalInfo.value?.approval_id;
    if (!id) return;
    await handleApprovalStream(() => api.streamReject(id), id);
  };

  const approveAllAction = async () => {
    if (!pendingApprovalInfo.value) return;
    const id = pendingApprovalInfo.value.approval_id;
    await updatePermissionProfile('full-auto');
    await handleApprovalStream(() => api.streamApproveAll(id), id);
  };

  return {
    approveAction,
    rejectAction,
    approveAllAction,
  };

  // ── 注：streamingPrefixTimeline 通过 options.streamingPrefixTimeline 共享给外部 ──
}
