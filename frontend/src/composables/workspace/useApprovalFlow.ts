import { type Ref } from 'vue';

import { api } from '../../api/client';
import type { AgentMessage, ApprovalInfo, StreamingItem, TraceRunSummary } from '../../types';
import { reconstructUiMessages, writeTimelineToStore } from './helpers';

interface ApprovalFlowOptions {
  sessions: Ref<any[]>;
  activeSessionId: Ref<string | null>;
  currentMessages: Ref<AgentMessage[]>;
  traceRuns: Ref<TraceRunSummary[]>;
  isStreaming: Ref<boolean>;
  isChatLoading: Ref<boolean>;
  streamingTimeline: Ref<StreamingItem[]>;
  lastCompletedRun: Ref<TraceRunSummary | null>;
  errorMsg: Ref<string | null>;
  isAwaitingApproval: Ref<boolean>;
  pendingApprovalInfo: Ref<ApprovalInfo | null>;
  onLiveAgentEvent: (sessionId: string, ev: any) => void;
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
    lastCompletedRun,
    errorMsg,
    isAwaitingApproval,
    pendingApprovalInfo,
    onLiveAgentEvent,
    extractChildAgents,
    updatePermissionProfile,
  } = options;

  async function handleApprovalStream(streamFn: () => AsyncGenerator<any>) {
    if (!pendingApprovalInfo.value) return;

    const initialTimeline: StreamingItem[] = [];
    for (let i = currentMessages.value.length - 1; i >= 0; i--) {
      const message = currentMessages.value[i];
      if (message.role === 'assistant' && message.timeline && message.timeline.length > 0) {
        initialTimeline.push(...message.timeline);
        break;
      }
    }

    isStreaming.value = true;
    isChatLoading.value = true;
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
        } else if (frame.type === 'agent_event') {
          if (frame.data.type !== 'final_answer') {
            streamingTimeline.value = [...streamingTimeline.value, { kind: 'event', event: frame.data }];
          }
          if (activeSessionId.value) {
            onLiveAgentEvent(activeSessionId.value, frame.data);
          }
        } else if (frame.type === 'paused') {
          stillAwaitingApproval = true;
          isAwaitingApproval.value = true;

          const partialTimeline = [...initialTimeline, ...streamingTimeline.value];
          if (capturedRunId) {
            writeTimelineToStore(capturedRunId, partialTimeline);
          }

          const partialText = partialTimeline
            .filter(i => i.kind === 'text')
            .map(i => i.content)
            .join('');
          if (partialText) {
            const newMsgs = [...currentMessages.value];
            for (let i = newMsgs.length - 1; i >= 0; i--) {
              if (newMsgs[i].role === 'assistant') {
                newMsgs[i] = { ...newMsgs[i], timeline: partialTimeline };
                break;
              }
            }
            currentMessages.value = newMsgs;
          }

          const nextApprovalId = frame.data.approval_id;
          if (nextApprovalId) {
            pendingApprovalInfo.value = {
              approval_id: nextApprovalId,
              tool_name: '',
              arguments: '',
              run_id: capturedRunId ?? '',
            };

            api.getApproval(nextApprovalId).then(info => {
              if (pendingApprovalInfo.value?.approval_id === nextApprovalId) {
                pendingApprovalInfo.value = {
                  approval_id: nextApprovalId,
                  tool_name: info.tool_name,
                  arguments: info.arguments,
                  run_id: capturedRunId ?? '',
                };
              }
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
      isAwaitingApproval.value = stillAwaitingApproval;
      if (!stillAwaitingApproval) {
        pendingApprovalInfo.value = null;
      }
      isStreaming.value = false;
      isChatLoading.value = false;
      streamingTimeline.value = [];
    }
  }

  const approveAction = async () => {
    if (!pendingApprovalInfo.value) return;
    const id = pendingApprovalInfo.value.approval_id;
    await handleApprovalStream(() => api.streamApprove(id));
  };

  const rejectAction = async () => {
    if (!pendingApprovalInfo.value) return;
    const id = pendingApprovalInfo.value.approval_id;
    await handleApprovalStream(() => api.streamReject(id));
  };

  const approveAllAction = async () => {
    if (!pendingApprovalInfo.value) return;
    const id = pendingApprovalInfo.value.approval_id;
    await updatePermissionProfile('full-auto');
    await handleApprovalStream(() => api.streamApproveAll(id));
  };

  return {
    approveAction,
    rejectAction,
    approveAllAction,
  };
}
