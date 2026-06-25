import { type Ref } from 'vue';

import { api } from '../../api/client';
import type { AgentMessage, ApprovalInfo, StreamUsageData, StreamingItem, TraceRunSummary } from '../../types';
import { removePendingApproval, upsertPendingApproval } from '../../utils/approvalQueue';
import { reconstructUiMessages, writeTimelineToStore } from './helpers';

interface SessionSpecificState {
  historyMessages: AgentMessage[];
  currentMessages: AgentMessage[];
  traceRuns: TraceRunSummary[];
  isChatLoading: boolean;
  isTraceLoading: boolean;
  isStreaming: boolean;
  streamingTimeline: StreamingItem[];
  streamingPrefixTimeline: StreamingItem[];
  streamingLatestUsage: StreamUsageData | null;
  lastCompletedRun: TraceRunSummary | null;
  errorMsg: string | null;
  isAwaitingApproval: boolean;
  pendingApprovalInfo: ApprovalInfo | null;
  pendingApprovalInfos: ApprovalInfo[];
  permissionProfile: string;
  streamAbortController: AbortController | null;
  pendingRunId: string | null;
  pendingUserInput: string;
  pendingAgentName: string | undefined;
  pendingSkillName: string | null;
}

interface ApprovalFlowOptions {
  sessions: Ref<any[]>;
  activeSessionId: Ref<string | null>;
  getSessionState: (sessionId: string) => SessionSpecificState;
  currentMessages: Ref<AgentMessage[]>;
  traceRuns: Ref<TraceRunSummary[]>;
  isStreaming: Ref<boolean>;
  isChatLoading: Ref<boolean>;
  streamingTimeline: Ref<StreamingItem[]>;
  streamingPrefixTimeline: Ref<StreamingItem[]>;
  streamingLatestUsage: Ref<StreamUsageData | null>;
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
    getSessionState,
    pendingApprovalInfo,
    isResolvingApproval,
    onLiveRunEvent,
    extractChildAgents,
    updatePermissionProfile,
  } = options;

  const syncApprovalHead = (state: SessionSpecificState) => {
    state.pendingApprovalInfo = state.pendingApprovalInfos[0] ?? null;
    state.isAwaitingApproval = state.pendingApprovalInfos.length > 0;
  };

  async function handleApprovalStream(streamFn: () => AsyncGenerator<any>, approvalId?: string) {
    const targetSessionId = activeSessionId.value;
    const targetApprovalId = approvalId ?? pendingApprovalInfo.value?.approval_id;
    if (!targetSessionId || !targetApprovalId) return;

    const state = getSessionState(targetSessionId);

    const initialTimeline: StreamingItem[] = [];
    for (let i = state.currentMessages.length - 1; i >= 0; i--) {
      const message = state.currentMessages[i];
      if (message.role === 'assistant' && message.timeline && message.timeline.length > 0) {
        initialTimeline.push(...message.timeline);
        break;
      }
    }

    state.pendingApprovalInfos = removePendingApproval(state.pendingApprovalInfos, targetApprovalId);
    syncApprovalHead(state);

    state.currentMessages = state.currentMessages
      .filter(m => !(m.role === 'assistant' && m.content === null))
      .map(m => {
        if (m.role === 'assistant' && m.timeline && m.timeline.length > 0) {
          return { ...m, timeline: [] };
        }
        return m;
      });

    state.isStreaming = true;
    state.isChatLoading = true;
    state.streamingPrefixTimeline = [...initialTimeline];
    state.streamingTimeline = [];
    state.streamingLatestUsage = null;
    state.errorMsg = null;
    isResolvingApproval.value = true;

    let capturedRunId: string | null = null;
    let stillAwaitingApproval = false;

    const upsertApprovalForState = (approval: ApprovalInfo) => {
      state.pendingApprovalInfos = upsertPendingApproval(state.pendingApprovalInfos, approval);
      syncApprovalHead(state);
    };

    try {
      for await (const frame of streamFn()) {
        if (frame.type === 'start' || frame.type === 'resume') {
          capturedRunId = frame.data.run_id;
        } else if (frame.type === 'delta') {
          const tl = state.streamingTimeline;
          const last = tl[tl.length - 1];
          if (last?.kind === 'text') {
            last.content += frame.data.content;
            state.streamingTimeline = [...tl];
          } else {
            state.streamingTimeline = [...tl, { kind: 'text', content: frame.data.content }];
          }
        } else if (frame.type === 'thinking_delta') {
          const tl = state.streamingTimeline;
          const last = tl[tl.length - 1];
          if (last?.kind === 'thinking') {
            last.content += frame.data.content;
            state.streamingTimeline = [...tl];
          } else {
            state.streamingTimeline = [...tl, { kind: 'thinking', content: frame.data.content }];
          }
        } else if (frame.type === 'run_event') {
          if (!['assistant_text', 'final_answer', 'thinking'].includes(frame.data.type)) {
            state.streamingTimeline = [...state.streamingTimeline, { kind: 'event', event: frame.data }];
          }
          if (frame.data.type === 'approval_required' && frame.data.content) {
            const nextApprovalId = frame.data.content;
            const pendingApproval = {
              approval_id: nextApprovalId,
              tool_name: frame.data.tool_name ?? '',
              arguments: '',
              run_id: capturedRunId ?? '',
              tool_call_id: frame.data.tool_call_id ?? undefined,
            };
            upsertApprovalForState(pendingApproval);

            api.getApproval(nextApprovalId).then(info => {
              upsertApprovalForState({
                approval_id: nextApprovalId,
                tool_name: info.tool_name ?? pendingApproval.tool_name,
                arguments: info.arguments ?? pendingApproval.arguments,
                run_id: capturedRunId ?? pendingApproval.run_id,
                tool_call_id: (info as any).tool_call_id ?? pendingApproval.tool_call_id,
              });
            }).catch(() => {});
          }
          onLiveRunEvent(targetSessionId, frame.data);
        } else if (frame.type === 'usage') {
          state.streamingLatestUsage = frame.data;
        } else if (frame.type === 'paused') {
          stillAwaitingApproval = true;
          state.isAwaitingApproval = true;
          isResolvingApproval.value = false;

          const partialTimeline = [...initialTimeline, ...state.streamingTimeline];
          if (capturedRunId) {
            writeTimelineToStore(capturedRunId, partialTimeline);
          }

          if (partialTimeline.length > 0) {
            const newMsgs = [...state.currentMessages];
            let found = false;
            for (let i = newMsgs.length - 1; i >= 0; i--) {
              const msg = newMsgs[i];
              if (msg.role === 'assistant' &&
                  (msg.content === null || (capturedRunId && msg.run_id === capturedRunId))) {
                newMsgs[i] = { ...msg, timeline: partialTimeline, run_id: capturedRunId ?? undefined };
                found = true;
                break;
              }
            }
            if (!found) {
              newMsgs.push({
                role: 'assistant',
                content: null,
                timeline: partialTimeline,
                run_id: capturedRunId ?? undefined
              });
            }
            state.currentMessages = newMsgs;
          }

          const nextApprovalId = frame.data.approval_id;
          if (nextApprovalId) {
            const pendingApproval = {
              approval_id: nextApprovalId,
              tool_name: '',
              arguments: '',
              run_id: capturedRunId ?? '',
            };
            upsertApprovalForState(pendingApproval);

            api.getApproval(nextApprovalId).then(info => {
              upsertApprovalForState({
                approval_id: nextApprovalId,
                tool_name: info.tool_name,
                arguments: info.arguments,
                run_id: capturedRunId ?? '',
                tool_call_id: (info as any).tool_call_id ?? undefined,
              });
            }).catch(() => {});
          }
        } else if (frame.type === 'end') {
          const frozenTimeline = [...initialTimeline, ...state.streamingTimeline];
          if (capturedRunId) {
            writeTimelineToStore(capturedRunId, frozenTimeline);
          }

          const [, traceResult] = await Promise.allSettled([
            api.getSessions().then(data => { sessions.value = data || []; }),
            api.getTrace(targetSessionId),
          ]);
          if (traceResult.status === 'fulfilled') {
            state.traceRuns = (traceResult.value as any).runs || [];
          }

          const activeMsgs = frame.data.state?.messages || [];
          state.currentMessages = reconstructUiMessages(state.traceRuns, activeMsgs);
          if (capturedRunId && frozenTimeline.length > 0) {
            for (let i = state.currentMessages.length - 1; i >= 0; i--) {
              if (state.currentMessages[i].role === 'assistant' && state.currentMessages[i].run_id === capturedRunId) {
                state.currentMessages[i] = { ...state.currentMessages[i], timeline: frozenTimeline };
                break;
              }
            }
          }
          extractChildAgents(targetSessionId, state.currentMessages, state.traceRuns);
          if (capturedRunId) {
            state.lastCompletedRun = state.traceRuns.find(r => r.run_id === capturedRunId) ?? null;
          }
        } else if (frame.type === 'error') {
          state.errorMsg = frame.data.message ?? 'Approval error';
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        state.errorMsg = 'Resume failed: ' + err.message;
      }
    } finally {
      isResolvingApproval.value = false;
      state.isAwaitingApproval = stillAwaitingApproval || state.pendingApprovalInfos.length > 0;
      state.pendingApprovalInfo = state.pendingApprovalInfos[0] ?? null;
      state.isStreaming = false;
      state.isChatLoading = false;
      state.streamingTimeline = [];
      state.streamingLatestUsage = null;
      state.streamingPrefixTimeline = [];
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
}
