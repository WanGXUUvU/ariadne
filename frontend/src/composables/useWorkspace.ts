import { ref, computed, watch } from 'vue';
import { api } from '../api/client';
import type {
  SessionSummary,
  AgentMessage,
  SkillMetadata,
  CompactResponse,
  TraceResponse,
  TraceRunSummary,
  StreamingItem,
} from '../types';
import type { ViewMode } from '../types/ui';
import { MOCK_AGENTS } from '../mock/ui-mocks';

const RESET_HISTORY_STORAGE_KEY = 'agent-build-reset-history-v1';
const TIMELINE_STORAGE_KEY = 'agent-build-timelines-v1';
const RESET_MARKER_CONTENT = '[RESET_MARKER]';

type ResetHistoryStore = Record<string, AgentMessage[]>;
type TimelineStore = Record<string, StreamingItem[]>;

function readTimelineStore(): TimelineStore {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(TIMELINE_STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw) as TimelineStore;
  } catch {
    return {};
  }
}

function writeTimelineToStore(runId: string, timeline: StreamingItem[]) {
  if (typeof window === 'undefined') return;
  const store = readTimelineStore();
  store[runId] = timeline;
  window.localStorage.setItem(TIMELINE_STORAGE_KEY, JSON.stringify(store));
}

function readResetHistoryStore(): ResetHistoryStore {
  if (typeof window === 'undefined') {
    return {};
  }

  try {
    const raw = window.localStorage.getItem(RESET_HISTORY_STORAGE_KEY);
    if (!raw) {
      return {};
    }

    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== 'object') {
      return {};
    }

    return parsed as ResetHistoryStore;
  } catch {
    return {};
  }
}

function writeResetHistoryStore(store: ResetHistoryStore) {
  if (typeof window === 'undefined') {
    return;
  }

  window.localStorage.setItem(RESET_HISTORY_STORAGE_KEY, JSON.stringify(store));
}

function readSessionResetHistory(sessionId: string): AgentMessage[] {
  return readResetHistoryStore()[sessionId] ?? [];
}

function writeSessionResetHistory(sessionId: string, messages: AgentMessage[]) {
  const store = readResetHistoryStore();

  if (messages.length === 0) {
    delete store[sessionId];
  } else {
    store[sessionId] = messages;
  }

  writeResetHistoryStore(store);
}

function clearSessionResetHistory(sessionId: string) {
  const store = readResetHistoryStore();
  if (!(sessionId in store)) {
    return;
  }

  delete store[sessionId];
  writeResetHistoryStore(store);
}

export function useWorkspace() {
  const activeView = ref<ViewMode>('chat');

  const sessions = ref<SessionSummary[]>([]);
  const activeSessionId = ref<string | null>(null);
  const currentMessages = ref<AgentMessage[]>([]);
  const historyMessages = ref<AgentMessage[]>([]);
  const traceRuns = ref<TraceRunSummary[]>([]);
  const skills = ref<SkillMetadata[]>([]);

  const activeAgentId = ref<string>(MOCK_AGENTS[0].id);

  const isInitializing = ref(true);
  const isChatLoading = ref(false);
  const isTraceLoading = ref(false);
  const isSkillsLoading = ref(false);
  const isCompacting = ref(false);
  const isStreaming = ref(false);
  const streamingTimeline = ref<StreamingItem[]>([]);  // 按到达顺序混排文字和工具事件

  // Stop 按钮相关状态
  const streamAbortController = ref<AbortController | null>(null);
  const pendingRunId = ref<string | null>(null);
  const pendingUserInput = ref<string>('');
  const pendingAgentName = ref<string | undefined>(undefined);
  const lastCompletedRun = ref<TraceRunSummary | null>(null);
  const errorMsg = ref<string | null>(null);
  const infoMsg = ref<string | null>(null);

  const messages = computed(() => [...historyMessages.value, ...currentMessages.value]);
  const activeSession = computed(() =>
    sessions.value.find((session) => session.session_id === activeSessionId.value) ?? null
  );

  const activeAgent = computed(() =>
    MOCK_AGENTS.find((a) => a.id === activeAgentId.value) ?? MOCK_AGENTS[0]
  );

  const loadSessions = async (preferredSessionId?: string | null) => {
    try {
      const data = await api.getSessions();
      sessions.value = data || [];

      if (preferredSessionId) {
        const matched = sessions.value.find((session) => session.session_id === preferredSessionId);
        if (matched) {
          activeSessionId.value = matched.session_id;
          return;
        }
      }

      if (!activeSessionId.value && sessions.value.length > 0) {
        activeSessionId.value = sessions.value[0].session_id;
      }
    } catch (err: any) {
      errorMsg.value = 'Failed to load sessions: ' + err.message;
    }
  };

  const loadTraceRuns = async (sessionId: string) => {
    isTraceLoading.value = true;
    try {
      const trace: TraceResponse = await api.getTrace(sessionId);
      traceRuns.value = trace.runs || [];
    } catch {
      traceRuns.value = [];
    } finally {
      isTraceLoading.value = false;
    }
  };

  const createNewSession = async () => {
    try {
      isChatLoading.value = true;
      const newSession = await api.createSession();
      await loadSessions(newSession.session_id);
      historyMessages.value = [];
      currentMessages.value = [];
      traceRuns.value = [];
      errorMsg.value = null;
    } catch (err: any) {
      errorMsg.value = 'Failed to create session: ' + err.message;
    } finally {
      isChatLoading.value = false;
    }
  };

  const loadSessionDetail = async (id: string) => {
    try {
      isChatLoading.value = true;
      isTraceLoading.value = true;
      const detail = await api.getSessionDetail(id);
      historyMessages.value = readSessionResetHistory(id);
      
      const msgs = detail.state?.messages || [];
      await loadTraceRuns(id);

      // 从本地存储恢复 timeline (交错视图)，保证刷新后视觉一致
      const timelineStore = readTimelineStore();
      if (traceRuns.value.length > 0) {
        for (let i = 0; i < msgs.length; i++) {
          if (msgs[i].role === 'assistant') {
            // 往前找对应的 user 消息，通过内容去匹配 trace run
            let correspondingRun: TraceRunSummary | undefined;
            for (let j = i - 1; j >= 0; j--) {
              if (msgs[j].role === 'user') {
                const userText = (msgs[j].content ?? '').trim();
                correspondingRun = traceRuns.value.find(r => r.user_input.trim() === userText);
                break;
              }
            }
            if (correspondingRun && timelineStore[correspondingRun.run_id]) {
              msgs[i] = { ...msgs[i], timeline: timelineStore[correspondingRun.run_id] };
            }
          }
        }
      }
      
      currentMessages.value = msgs;
      errorMsg.value = null;
    } catch (err: any) {
      if (err.message.includes('not found') || err.message.includes('404')) {
        activeSessionId.value = null;
        historyMessages.value = [];
        currentMessages.value = [];
        traceRuns.value = [];
      } else {
        errorMsg.value = 'Failed to load session details: ' + err.message;
      }
    } finally {
      isChatLoading.value = false;
      isTraceLoading.value = false;
    }
  };

  const sendMessage = async (input: string) => {
    if (!activeSessionId.value) return;

    isChatLoading.value = true;
    isStreaming.value = true;
    streamingTimeline.value = [];
    lastCompletedRun.value = null;
    errorMsg.value = null;

    currentMessages.value.push({ role: 'user', content: input });

    let capturedRunId: string | null = null;
    const abortController = new AbortController();
    streamAbortController.value = abortController;
    pendingUserInput.value = input;
    pendingAgentName.value = activeAgent.value?.id;

    try {
      for await (const frame of api.streamRun(activeSessionId.value, input, activeAgent.value?.id, abortController.signal)) {
        if (frame.type === 'start') {
          capturedRunId = frame.data.run_id;
          pendingRunId.value = capturedRunId;
        } else if (frame.type === 'delta') {
          // 追加到最后一个 text 项，或新建一个 text 项
          const tl = streamingTimeline.value;
          const last = tl[tl.length - 1];
          if (last?.kind === 'text') {
            last.content += frame.data.content;
            streamingTimeline.value = [...tl];   // 触发响应式
          } else {
            streamingTimeline.value = [...tl, { kind: 'text', content: frame.data.content }];
          }
        } else if (frame.type === 'agent_event') {
          // 工具事件直接追加（跳过 final_answer，那是文字回答的元数据）
          if (frame.data.type !== 'final_answer') {
            streamingTimeline.value = [...streamingTimeline.value, { kind: 'event', event: frame.data }];
          }
        } else if (frame.type === 'end') {
          // 冻结时间线，patch 进新消息里，再替换 currentMessages
          const frozenTimeline = [...streamingTimeline.value];
          if (capturedRunId) {
            writeTimelineToStore(capturedRunId, frozenTimeline);
          }
          const newMsgs = [...(frame.data.state?.messages ?? currentMessages.value)];
          for (let i = newMsgs.length - 1; i >= 0; i--) {
            if (newMsgs[i].role === 'assistant') {
              newMsgs[i] = { ...newMsgs[i], timeline: frozenTimeline };
              break;
            }
          }
          currentMessages.value = newMsgs;
          // 只刷新 sessions 列表（更新预览文字），不传 preferredSessionId 避免触发 watch → loadSessionDetail
          // loadSessionDetail 会覆盖 currentMessages，把刚写入的 timeline 冲掉
          const [, traceResult] = await Promise.allSettled([
            api.getSessions().then(data => { sessions.value = data || []; }),
            api.getTrace(activeSessionId.value!),
          ]);
          if (traceResult.status === 'fulfilled') {
            traceRuns.value = (traceResult.value as any).runs || [];
          }
          if (capturedRunId) {
            lastCompletedRun.value = traceRuns.value.find(r => r.run_id === capturedRunId) ?? null;
          }
        } else if (frame.type === 'error') {
          errorMsg.value = frame.data.message ?? 'Streaming error';
        }
      }
    } catch (err: any) {
      // AbortError 是用户主动 Stop，不是错误，静默处理
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

    // 1. 截取当前已输出的内容
    const partialReply = streamingTimeline.value
      .filter(item => item.kind === 'text')
      .map(item => item.content)
      .join('');
    const runId = pendingRunId.value;
    const sessionId = activeSessionId.value;
    const userInput = pendingUserInput.value;
    const agentName = pendingAgentName.value;

    // 2. 中止 SSE
    streamAbortController.value.abort();

    // 3. 如果已有 run_id，调 finalize 接口落库
    if (runId && sessionId && userInput) {
      try {
        await api.finalizeRun(sessionId, runId, userInput, partialReply, agentName);
      } catch {
        // finalize 失败不阻塞 UI
      }
    }

    // 4. 把截断内容追加到对话框，标记 stopped=true
    if (partialReply) {
      currentMessages.value = [
        ...currentMessages.value,
        { role: 'assistant', content: partialReply, stopped: true },
      ];
    }
  };

  const compactSession = async () => {
    if (!activeSessionId.value) return;
    try {
      isCompacting.value = true;
      errorMsg.value = null;
      const result: CompactResponse = await api.compactSession(activeSessionId.value);
      await loadSessionDetail(activeSessionId.value);
      await loadSessions(activeSessionId.value);
      if (result?.did_compact === false) {
        infoMsg.value = '✓ Context is already up to date — no compaction needed.';
      } else {
        infoMsg.value = `✓ Context compacted. ${result?.removed_count ?? ''} messages summarized.`;
      }
      setTimeout(() => {
        infoMsg.value = null;
      }, 3000);
    } catch (err: any) {
      errorMsg.value = 'Compact failed: ' + err.message;
    } finally {
      isCompacting.value = false;
    }
  };

  const deleteSession = async (id: string) => {
    try {
      await api.deleteSession(id);
      clearSessionResetHistory(id);
      if (activeSessionId.value === id) {
        activeSessionId.value = null;
        historyMessages.value = [];
        currentMessages.value = [];
        traceRuns.value = [];
      }
      await loadSessions();
    } catch (err: any) {
      errorMsg.value = 'Delete failed: ' + err.message;
    }
  };

  const renameSession = async (id: string, newName: string) => {
    try {
      await api.renameSession(id, newName);
      await loadSessions();
    } catch (err: any) {
      errorMsg.value = 'Rename failed: ' + err.message;
    }
  };

  const resetSession = async () => {
    if (!activeSessionId.value) return;
    try {
      const currentId = activeSessionId.value;
      await api.resetSession(currentId);
      historyMessages.value = [
        ...historyMessages.value,
        ...currentMessages.value,
        { role: 'system', content: RESET_MARKER_CONTENT },
      ];
      writeSessionResetHistory(currentId, historyMessages.value);
      currentMessages.value = [];
      traceRuns.value = [];
      await loadSessions(currentId);
    } catch (err: any) {
      errorMsg.value = 'Reset failed: ' + err.message;
    }
  };

  const loadSkills = async () => {
    try {
      isSkillsLoading.value = true;
      skills.value = await api.getSkills();
    } catch (err: any) {
      errorMsg.value = 'Failed to load skills: ' + err.message;
    } finally {
      isSkillsLoading.value = false;
    }
  };

  const toggleSkill = async (skillName: string, currentlyEnabled: boolean) => {
    try {
      if (currentlyEnabled) {
        await api.disableSkill(skillName);
      } else {
        await api.enableSkill(skillName);
      }
      await loadSkills();
    } catch (err: any) {
      errorMsg.value = 'Failed to toggle skill: ' + err.message;
    }
  };

  const initializeWorkspace = async () => {
    isInitializing.value = true;
    await Promise.all([loadSessions(), loadSkills()]);
    isInitializing.value = false;
  };

  watch(activeSessionId, (newId, _oldId) => {
    // streaming 进行中 / 刚结束时，end 帧已经自行更新了 currentMessages（含 timeline），
    // 此时绝不能触发 loadSessionDetail，否则后端返回的纯消息会覆盖 timeline。
    if (isStreaming.value || isChatLoading.value) return;
    if (newId) {
      loadSessionDetail(newId);
    } else {
      historyMessages.value = [];
      currentMessages.value = [];
      traceRuns.value = [];
    }
  });

  return {
    activeView,
    sessions,
    activeSessionId,
    activeSession,
    messages,
    traceRuns,
    skills,
    activeAgentId,
    activeAgent,
    isInitializing,
    isChatLoading,
    isTraceLoading,
    isSkillsLoading,
    isCompacting,
    isStreaming,
    streamingTimeline,
    lastCompletedRun,
    errorMsg,
    infoMsg,
    initializeWorkspace,
    createNewSession,
    sendMessage,
    stopStreaming,
    compactSession,
    resetSession,
    deleteSession,
    renameSession,
    toggleSkill,
    availableAgents: MOCK_AGENTS,
  };
}
