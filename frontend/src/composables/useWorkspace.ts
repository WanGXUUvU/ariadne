import { ref, computed, watch } from 'vue';
import { api } from '../api/client';
import type { SessionSummary, AgentMessage, AgentEvent, SkillMetadata, CompactResponse, TraceResponse } from '../types';
import type { ViewMode } from '../types/ui';
import { MOCK_AGENTS } from '../mock/ui-mocks';

const RESET_HISTORY_STORAGE_KEY = 'agent-build-reset-history-v1';
const RESET_MARKER_CONTENT = '[RESET_MARKER]';

type ResetHistoryStore = Record<string, AgentMessage[]>;

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
  // Global View State
  const activeView = ref<ViewMode>('chat');

  // Data States
  const sessions = ref<SessionSummary[]>([]);
  const activeSessionId = ref<string | null>(null);
  const currentMessages = ref<AgentMessage[]>([]);
  const historyMessages = ref<AgentMessage[]>([]);
  const events = ref<AgentEvent[]>([]);
  const skills = ref<SkillMetadata[]>([]);
  
  // Selection States
  const activeAgentId = ref<string>(MOCK_AGENTS[0].id);

  // Loading & Error States
  const isInitializing = ref(true);
  const isChatLoading = ref(false);
  const isTraceLoading = ref(false);
  const isSkillsLoading = ref(false);
  const isCompacting = ref(false);
  const errorMsg = ref<string | null>(null);
  const infoMsg = ref<string | null>(null); // 成功/信息类提示，绿色显示，与 errorMsg 分开

  // Computed Properties
  const messages = computed(() => [...historyMessages.value, ...currentMessages.value]);
  const activeSession = computed(() =>
    sessions.value.find((session) => session.session_id === activeSessionId.value) ?? null
  );

  const activeAgent = computed(() => 
    MOCK_AGENTS.find(a => a.id === activeAgentId.value) ?? MOCK_AGENTS[0]
  );

  // --- ACTIONS ---

  // Sessions
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

  const createNewSession = async () => {
    try {
      isChatLoading.value = true;
      const newSession = await api.createSession();
      await loadSessions(newSession.session_id);
      historyMessages.value = [];
      currentMessages.value = [];
      events.value = [];
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
      const [detail, trace] = await Promise.all([
        api.getSessionDetail(id),
        api.getTrace(id).catch(() => []) // Fallback if trace API fails
      ]);
      historyMessages.value = readSessionResetHistory(id);
      currentMessages.value = detail.state?.messages || [];
      // Flatten all events from all runs in the TraceResponse
      if (trace && 'runs' in trace) {
        events.value = (trace as TraceResponse).runs.flatMap((run: any) => run.events);
      } else {
        events.value = [];
      }
      errorMsg.value = null;
    } catch (err: any) {
      if (err.message.includes('not found') || err.message.includes('404')) {
        activeSessionId.value = null;
        historyMessages.value = [];
        currentMessages.value = [];
        events.value = [];
      } else {
        errorMsg.value = 'Failed to load session details: ' + err.message;
      }
    } finally {
      isChatLoading.value = false;
      isTraceLoading.value = false;
    }
  };

  // Chat
  const sendMessage = async (input: string) => {
    if (!activeSessionId.value) return;
    try {
      if (currentMessages.value.length > 12) {
        isCompacting.value = true;
      }
      isChatLoading.value = true;
      errorMsg.value = null;
      // Add pessimistic message
      currentMessages.value.push({ role: 'user', content: input });
      
      const res = await api.runPass(activeSessionId.value, input, activeAgent.value?.id);
      currentMessages.value = res.state?.messages || [];
      // append new events to trace
      if (res.events && res.events.length > 0) {
        events.value = [...events.value, ...res.events];
      }
    } catch (err: any) {
      errorMsg.value = 'Run failed: ' + err.message;
    } finally {
      isChatLoading.value = false;
      isCompacting.value = false;
    }
  };

  const compactSession = async () => {
    if (!activeSessionId.value) return;
    try {
      isCompacting.value = true;
      errorMsg.value = null; // 清除旧错误
      const result: CompactResponse = await api.compactSession(activeSessionId.value);
      await loadSessionDetail(activeSessionId.value); // 刷新聊天消息列表
      await loadSessions(activeSessionId.value);       // 同步刷新 sidebar 的 message_count
      // 根据后端返回的 did_compact 给用户反馈
      if (result?.did_compact === false) {
        infoMsg.value = '✓ Context is already up to date — no compaction needed.';
      } else {
        infoMsg.value = `✓ Context compacted. ${result?.removed_count ?? ''} messages summarized.`;
      }
      // 3 秒后自动清除提示
      setTimeout(() => { infoMsg.value = null; }, 3000);
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
        events.value = [];
      }
      await loadSessions();
    } catch (err: any) {
      errorMsg.value = 'Delete failed: ' + err.message;
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
        { role: 'system', content: RESET_MARKER_CONTENT }
      ];
      writeSessionResetHistory(currentId, historyMessages.value);
      currentMessages.value = [];
      events.value = [];
      await loadSessions(currentId);
    } catch (err: any) {
      errorMsg.value = 'Reset failed: ' + err.message;
    }
  };

  // Skills
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
      await loadSkills(); // Refresh
    } catch (err: any) {
      errorMsg.value = 'Failed to toggle skill: ' + err.message;
    }
  };

  // Lifecycle
  const initializeWorkspace = async () => {
    isInitializing.value = true;
    await Promise.all([
      loadSessions(),
      loadSkills()
    ]);
    isInitializing.value = false;
  };

  // Watchers
  watch(activeSessionId, (newId) => {
    if (newId) {
      loadSessionDetail(newId);
    } else {
      historyMessages.value = [];
      currentMessages.value = [];
      events.value = [];
    }
  });

  return {
    // State
    activeView,
    sessions,
    activeSessionId,
    activeSession,
    messages,
    events,
    skills,
    activeAgentId,
    activeAgent,
    
    // Status
    isInitializing,
    isChatLoading,
    isTraceLoading,
    isSkillsLoading,
    isCompacting,
    errorMsg,
    infoMsg, // 成功/信息类提示

    // Actions
    initializeWorkspace,
    createNewSession,
    sendMessage,
    compactSession,
    resetSession,
    deleteSession,
    toggleSkill,
    
    // Mock Data
    availableAgents: MOCK_AGENTS
  };
}
