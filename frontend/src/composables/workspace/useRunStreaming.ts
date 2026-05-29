import { type ComputedRef, type Ref } from 'vue';

import { api } from '../../api/client';
import type {
  AgentMessage,
  ApprovalInfo,
  StreamingItem,
  TraceRunSummary,
} from '../../types';
import type { UiAgentOption } from '../../types/ui';
import { reconstructUiMessages, writeTimelineToStore } from './helpers';

interface RunStreamingOptions {
  sessions: Ref<any[]>;
  activeSessionId: Ref<string | null>;
  currentMessages: Ref<AgentMessage[]>;
  traceRuns: Ref<TraceRunSummary[]>;
  isChatLoading: Ref<boolean>;
  isStreaming: Ref<boolean>;
  streamingTimeline: Ref<StreamingItem[]>;
  lastCompletedRun: Ref<TraceRunSummary | null>;
  errorMsg: Ref<string | null>;
  isAwaitingApproval: Ref<boolean>;
  pendingApprovalInfo: Ref<ApprovalInfo | null>;
  activeAgent: ComputedRef<UiAgentOption | null>;
  pendingRunId: Ref<string | null>;
  pendingUserInput: Ref<string>;
  pendingAgentName: Ref<string | undefined>;
  streamAbortController: Ref<AbortController | null>;
  onLiveAgentEvent: (sessionId: string, ev: any) => void;
  extractChildAgents: (sessionId: string, msgs: AgentMessage[], traceRuns: TraceRunSummary[]) => void;
}

export function useRunStreaming(options: RunStreamingOptions) {
  const {
    sessions,
    activeSessionId,
    currentMessages,
    traceRuns,
    isChatLoading,
    isStreaming,
    streamingTimeline,
    lastCompletedRun,
    errorMsg,
    isAwaitingApproval,
    pendingApprovalInfo,
    activeAgent,
    pendingRunId,
    pendingUserInput,
    pendingAgentName,
    streamAbortController,
    onLiveAgentEvent,
    extractChildAgents,
  } = options;

  const sendMessage = async (input: string, skillName?: string | null) => {
    if (!activeSessionId.value) return;

    isChatLoading.value = true;
    isStreaming.value = true;
    streamingTimeline.value = [];
    lastCompletedRun.value = null;
    errorMsg.value = null;

    currentMessages.value.push({ role: 'user', content: input, skill_name: skillName ?? null });

    let capturedRunId: string | null = null;
    const abortController = new AbortController();
    streamAbortController.value = abortController;
    pendingUserInput.value = input;
    pendingAgentName.value = activeAgent.value?.id;

    try {
      for await (const frame of api.streamRun(activeSessionId.value, input, activeAgent.value?.id, skillName, abortController.signal)) {
        if (frame.type === 'start') {
          capturedRunId = frame.data.run_id;
          pendingRunId.value = capturedRunId;
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
          if (frame.data.type === 'approval_required' && frame.data.content) {
            const approvalId = frame.data.content;
            pendingApprovalInfo.value = {
              approval_id: approvalId,
              tool_name: frame.data.tool_name ?? '',
              arguments: '',
              run_id: capturedRunId ?? '',
            };
            api.getApproval(approvalId).then(info => {
              if (pendingApprovalInfo.value?.approval_id === approvalId) {
                pendingApprovalInfo.value = { ...pendingApprovalInfo.value, arguments: info.arguments };
              }
            }).catch(() => {});
          }
          if (activeSessionId.value) {
            onLiveAgentEvent(activeSessionId.value, frame.data);
          }
        } else if (frame.type === 'paused') {
          isAwaitingApproval.value = true;
          const partialTimeline = [...streamingTimeline.value];
          if (capturedRunId) {
            writeTimelineToStore(capturedRunId, partialTimeline);
          }
          const partialText = partialTimeline
            .filter(i => i.kind === 'text')
            .map(i => i.content)
            .join('');
          const newMsgs = [...currentMessages.value];
          if (partialText) {
            for (let i = newMsgs.length - 1; i >= 0; i--) {
              if (newMsgs[i].role === 'assistant') {
                newMsgs[i] = { ...newMsgs[i], timeline: partialTimeline };
                break;
              }
            }
          }
          currentMessages.value = newMsgs;
        } else if (frame.type === 'end') {
          const frozenTimeline = [...streamingTimeline.value];
          if (capturedRunId) {
            writeTimelineToStore(capturedRunId, frozenTimeline);
          }
          const [, traceResult] = await Promise.allSettled([
            api.getSessions().then(data => { sessions.value = data || []; }),
            api.getTrace(activeSessionId.value!),
          ]);
          if (traceResult.status === 'fulfilled') {
            traceRuns.value = (traceResult.value as any).runs || [];
          }
          const activeMsgs = frame.data.state?.messages || [];
          currentMessages.value = reconstructUiMessages(traceRuns.value, activeMsgs);
          if (activeSessionId.value) {
            extractChildAgents(activeSessionId.value, currentMessages.value, traceRuns.value);
          }
          if (capturedRunId) {
            lastCompletedRun.value = traceRuns.value.find(r => r.run_id === capturedRunId) ?? null;
          }
        } else if (frame.type === 'error') {
          errorMsg.value = frame.data.message ?? 'Streaming error';
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        errorMsg.value = 'Run failed: ' + err.message;
      }
    } finally {
      isChatLoading.value = false;
      isStreaming.value = false;
      streamingTimeline.value = [];
      streamAbortController.value = null;
      pendingRunId.value = null;
    }
  };

  const stopStreaming = async () => {
    if (!isStreaming.value || !streamAbortController.value) return;
    const frozenTimeline = [...streamingTimeline.value];
    const partialReply = frozenTimeline
      .filter(item => item.kind === 'text')
      .map(item => item.content)
      .join('');
    const runId = pendingRunId.value;
    const sessionId = activeSessionId.value;
    const userInput = pendingUserInput.value;
    const agentName = pendingAgentName.value;

    if (runId && frozenTimeline.length > 0) {
      writeTimelineToStore(runId, frozenTimeline);
    }

    streamAbortController.value.abort();

    if (runId && sessionId && userInput) {
      try {
        await api.finalizeRun(sessionId, runId, userInput, partialReply, agentName);
      } catch {
        // finalize failure should not block UI
      }
    }

    if (partialReply.trim() || frozenTimeline.length > 0) {
      currentMessages.value = [
        ...currentMessages.value,
        { role: 'assistant', content: partialReply || null, stopped: true, timeline: frozenTimeline },
      ];
    }
  };

  return {
    sendMessage,
    stopStreaming,
  };
}
