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
  pendingApprovalInfos: Ref<ApprovalInfo[]>;
  activeAgent: ComputedRef<UiAgentOption | null>;
  pendingRunId: Ref<string | null>;
  pendingUserInput: Ref<string>;
  pendingAgentName: Ref<string | undefined>;
  pendingSkillName: Ref<string | null>;
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
    pendingApprovalInfos,
    activeAgent,
    pendingRunId,
    pendingUserInput,
    pendingAgentName,
    pendingSkillName,
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
    pendingSkillName.value = skillName ?? null;

    try {
      for await (const frame of api.streamRun(activeSessionId.value, input, activeAgent.value?.id, skillName, abortController.signal)) {
        if (frame.type === 'start') {
          capturedRunId = frame.data.run_id;
          pendingRunId.value = capturedRunId;
        } else if (frame.type === 'delta') {
          // 打字机效果流式延迟支持
          const delayMs = parseInt(localStorage.getItem('settings-stream-delay') || '10');
          if (delayMs > 0) {
            await new Promise(resolve => setTimeout(resolve, delayMs));
          }
          const tl = streamingTimeline.value;
          const last = tl[tl.length - 1];
          if (last?.kind === 'text') {
            last.content += frame.data.content;
            streamingTimeline.value = [...tl];
          } else {
            streamingTimeline.value = [...tl, { kind: 'text', content: frame.data.content }];
          }
        } else if (frame.type === 'thinking_delta') {
          // 打字机效果流式延迟支持
          const delayMs = parseInt(localStorage.getItem('settings-stream-delay') || '10');
          if (delayMs > 0) {
            await new Promise(resolve => setTimeout(resolve, delayMs));
          }
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
            const pendingApproval = {
              approval_id: approvalId,
              tool_name: frame.data.tool_name ?? '',
              arguments: '',
              run_id: capturedRunId ?? '',
              tool_call_id: frame.data.tool_call_id ?? undefined,
            };
            pendingApprovalInfos.value = upsertPendingApproval(pendingApprovalInfos.value, pendingApproval);
            pendingApprovalInfo.value = pendingApprovalInfos.value[0] ?? null;
            api.getApproval(approvalId).then(info => {
              pendingApprovalInfos.value = upsertPendingApproval(pendingApprovalInfos.value, {
                approval_id: approvalId,
                tool_name: info.tool_name ?? pendingApproval.tool_name,
                arguments: info.arguments ?? pendingApproval.arguments,
                run_id: capturedRunId ?? pendingApproval.run_id,
                tool_call_id: (info as any).tool_call_id ?? pendingApproval.tool_call_id,
              });
              pendingApprovalInfo.value = pendingApprovalInfos.value[0] ?? null;
            }).catch(() => {});
          }
          if (activeSessionId.value) {
            onLiveAgentEvent(activeSessionId.value, frame.data);
          }
        } else if (frame.type === 'paused') {
          isAwaitingApproval.value = true;
          pendingApprovalInfo.value = pendingApprovalInfos.value[0] ?? pendingApprovalInfo.value;
          const partialTimeline = [...streamingTimeline.value];
          if (capturedRunId) {
            writeTimelineToStore(capturedRunId, partialTimeline);
          }
          const newMsgs = [...currentMessages.value];
          // ── 只更新当前 run 对应的占位消息或 run_id 匹配的 assistant 消息 ──
          // 绝不修改其他历史轮次的 assistant 消息，避免审批 UI 出现在错误的对话里
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
            // 没有找到本轮占位消息（纯工具流首次 paused），插入新占位
            if (!found) {
              newMsgs.push({ role: 'assistant', content: null, timeline: partialTimeline });
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
          throw new Error(frame.data.message ?? 'Streaming error');
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        errorMsg.value = 'Run failed: ' + err.message;
        const frozenTimeline = [...streamingTimeline.value];
        const partialReply = frozenTimeline
          .filter(item => item.kind === 'text')
          .map(item => item.content)
          .join('');
        if (partialReply.trim() || frozenTimeline.length > 0) {
          let updated = false;
          const newMsgs = [...currentMessages.value];
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
          currentMessages.value = newMsgs;
        }
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
