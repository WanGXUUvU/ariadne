import { type ComputedRef, type Ref } from 'vue';

import { api } from '../../api/client';
import type {
  AgentMessage,
  ApprovalInfo,
  StreamingItem,
  TraceRunSummary,
} from '../../types';
import type { UiAgentOption } from '../../types/ui';
import { upsertPendingApproval } from '../../utils/approvalQueue';
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

interface RunStreamingOptions {
  sessions: Ref<any[]>;
  activeSessionId: Ref<string | null>;
  getSessionState: (sessionId: string) => SessionSpecificState;
  activeAgent: ComputedRef<UiAgentOption | null>;
  onLiveAgentEvent: (sessionId: string, ev: any) => void;
  extractChildAgents: (sessionId: string, msgs: AgentMessage[], traceRuns: TraceRunSummary[]) => void;
}

export function useRunStreaming(options: RunStreamingOptions) {
  const {
    sessions,
    activeSessionId,
    getSessionState,
    activeAgent,
    onLiveAgentEvent,
    extractChildAgents,
  } = options;

  const sendMessage = async (input: string, skillName?: string | null) => {
    if (!activeSessionId.value) return;

    const targetSessionId = activeSessionId.value;
    const state = getSessionState(targetSessionId);

    state.isChatLoading = true;
    state.isStreaming = true;
    state.streamingTimeline = [];
    state.lastCompletedRun = null;
    state.errorMsg = null;

    state.currentMessages.push({ role: 'user', content: input, skill_name: skillName ?? null });

    let capturedRunId: string | null = null;
    const abortController = new AbortController();
    state.streamAbortController = abortController;
    state.pendingUserInput = input;
    state.pendingAgentName = activeAgent.value?.id;
    state.pendingSkillName = skillName ?? null;

    try {
      for await (const frame of api.streamRun(targetSessionId, input, activeAgent.value?.id, skillName, abortController.signal)) {
        if (frame.type === 'start') {
          capturedRunId = frame.data.run_id;
          state.pendingRunId = capturedRunId;
        } else if (frame.type === 'delta') {
          // 打字机效果流式延迟支持
          const delayMs = parseInt(localStorage.getItem('settings-stream-delay') || '10');
          if (delayMs > 0) {
            await new Promise(resolve => setTimeout(resolve, delayMs));
          }
          const tl = state.streamingTimeline;
          const last = tl[tl.length - 1];
          if (last?.kind === 'text') {
            last.content += frame.data.content;
            state.streamingTimeline = [...tl];
          } else {
            state.streamingTimeline = [...tl, { kind: 'text', content: frame.data.content }];
          }
        } else if (frame.type === 'thinking_delta') {
          // 打字机效果流式延迟支持
          const delayMs = parseInt(localStorage.getItem('settings-stream-delay') || '10');
          if (delayMs > 0) {
            await new Promise(resolve => setTimeout(resolve, delayMs));
          }
          const tl = state.streamingTimeline;
          const last = tl[tl.length - 1];
          if (last?.kind === 'thinking') {
            last.content += frame.data.content;
            state.streamingTimeline = [...tl];
          } else {
            state.streamingTimeline = [...tl, { kind: 'thinking', content: frame.data.content }];
          }
        } else if (frame.type === 'agent_event') {
          if (frame.data.type !== 'final_answer') {
            state.streamingTimeline = [...state.streamingTimeline, { kind: 'event', event: frame.data }];
          }
          if (frame.data.type === 'approval_required' && frame.data.content) {
            const approvalId = frame.data.content;
            const pendingApproval = {
              approval_id: approvalId,
              tool_name: frame.data.tool_name ?? '',
              arguments: '',
              run_id: capturedRunId ?? '',
              tool_call_id: frame.data.tool_call_id ?? undefined,
            };
            state.pendingApprovalInfos = upsertPendingApproval(state.pendingApprovalInfos, pendingApproval);
            state.pendingApprovalInfo = state.pendingApprovalInfos[0] ?? null;
            api.getApproval(approvalId).then(info => {
              state.pendingApprovalInfos = upsertPendingApproval(state.pendingApprovalInfos, {
                approval_id: approvalId,
                tool_name: info.tool_name ?? pendingApproval.tool_name,
                arguments: info.arguments ?? pendingApproval.arguments,
                run_id: capturedRunId ?? pendingApproval.run_id,
                tool_call_id: (info as any).tool_call_id ?? pendingApproval.tool_call_id,
              });
              state.pendingApprovalInfo = state.pendingApprovalInfos[0] ?? null;
            }).catch(() => {});
          }
          onLiveAgentEvent(targetSessionId, frame.data);
        } else if (frame.type === 'paused') {
          state.isAwaitingApproval = true;
          state.pendingApprovalInfo = state.pendingApprovalInfos[0] ?? state.pendingApprovalInfo;
          const partialTimeline = [...state.streamingTimeline];
          if (capturedRunId) {
            writeTimelineToStore(capturedRunId, partialTimeline);
          }
          const newMsgs = [...state.currentMessages];
          if (partialTimeline.length > 0) {
            let found = false;
            for (let i = newMsgs.length - 1; i >= 0; i--) {
              const msg = newMsgs[i];
              if (msg.role === 'assistant' &&
                  (msg.content === null || (capturedRunId && msg.run_id === capturedRunId))) {
                newMsgs[i] = { ...msg, timeline: partialTimeline };
                found = true;
                break;
              }
            }
            if (!found) {
              newMsgs.push({ role: 'assistant', content: null, timeline: partialTimeline });
            }
          }
          state.currentMessages = newMsgs;
        } else if (frame.type === 'end') {
          const frozenTimeline = [...state.streamingTimeline];
          if (capturedRunId) {
            writeTimelineToStore(capturedRunId, frozenTimeline);
          }
          const [, traceResult] = await Promise.allSettled([
            api.getSessions().then(data => { sessions.value = data || []; }),
            api.getTrace(targetSessionId),
          ]);
          let fetchedRuns: TraceRunSummary[] = [];
          if (traceResult.status === 'fulfilled') {
            fetchedRuns = (traceResult.value as any).runs || [];
          }
          const activeMsgs = frame.data.state?.messages || [];
          state.traceRuns = fetchedRuns;
          state.currentMessages = reconstructUiMessages(state.traceRuns, activeMsgs);
          extractChildAgents(targetSessionId, state.currentMessages, state.traceRuns);
          if (capturedRunId) {
            state.lastCompletedRun = state.traceRuns.find(r => r.run_id === capturedRunId) ?? null;
          }
        } else if (frame.type === 'error') {
          state.errorMsg = frame.data.message ?? 'Streaming error';
          throw new Error(frame.data.message ?? 'Streaming error');
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        state.errorMsg = 'Run failed: ' + err.message;
        const frozenTimeline = [...state.streamingTimeline];
        const partialReply = frozenTimeline
          .filter(item => item.kind === 'text')
          .map(item => item.content)
          .join('');
        if (partialReply.trim() || frozenTimeline.length > 0) {
          let updated = false;
          const newMsgs = [...state.currentMessages];
          for (let i = newMsgs.length - 1; i >= 0; i--) {
            const msg = newMsgs[i];
            if (msg.role === 'assistant' && (msg.content === null || (capturedRunId && msg.run_id === capturedRunId))) {
              newMsgs[i] = {
                ...msg,
                content: partialReply || null,
                stopped: true,
                timeline: frozenTimeline
              };
              updated = true;
              break;
            }
          }
          if (!updated) {
            newMsgs.push({
              role: 'assistant',
              content: partialReply || null,
              stopped: true,
              timeline: frozenTimeline
            });
          }
          state.currentMessages = newMsgs;
        }
      }
    } finally {
      state.isChatLoading = false;
      state.isStreaming = false;
      state.streamingTimeline = [];
      state.streamAbortController = null;
      state.pendingRunId = null;
    }
  };

  const stopStreaming = async () => {
    if (!activeSessionId.value) return;
    const sessionId = activeSessionId.value;
    const state = getSessionState(sessionId);

    if (!state.isStreaming || !state.streamAbortController) return;
    const frozenTimeline = [...state.streamingTimeline];
    const partialReply = frozenTimeline
      .filter(item => item.kind === 'text')
      .map(item => item.content)
      .join('');
    const runId = state.pendingRunId;
    const userInput = state.pendingUserInput;
    const agentName = state.pendingAgentName;

    if (runId && frozenTimeline.length > 0) {
      writeTimelineToStore(runId, frozenTimeline);
    }

    // Immediately stop the streaming visual state for the UI
    state.isStreaming = false;
    state.streamingTimeline = [];

    state.streamAbortController.abort();

    if (runId && sessionId && userInput) {
      try {
        await api.finalizeRun(sessionId, runId, userInput, partialReply, agentName);
      } catch {
        // finalize failure should not block UI
      }
    }

    if (partialReply.trim() || frozenTimeline.length > 0) {
      state.currentMessages = [
        ...state.currentMessages,
        { role: 'assistant', content: partialReply || null, stopped: true, timeline: frozenTimeline },
      ];
    }
  };

  return {
    sendMessage,
    stopStreaming,
  };
}
