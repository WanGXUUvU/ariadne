import { ref, computed, watch } from 'vue';
import { api } from '../api/client';
import type { SessionSummary, AgentMessage, AgentEvent, SkillMetadata, CompactResponse } from '../types';
import type { ViewMode, UiAgentOption } from '../types/ui';
import { MOCK_AGENTS } from '../mock/ui-mocks';

export function useWorkspace() {
  // Global View State
  const activeView = ref<ViewMode>('chat');

  // Data States
  const sessions = ref<SessionSummary[]>([]);
  const activeSessionId = ref<string | null>(null);
  const messages = ref<AgentMessage[]>([]);
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
      messages.value = [];
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
      messages.value = detail.state?.messages || [];
      // Flatten all events from all runs in the TraceResponse
      if (trace && trace.runs) {
        events.value = trace.runs.flatMap((run: any) => run.events);
      } else {
        events.value = [];
      }
      errorMsg.value = null;
    } catch (err: any) {
      if (err.message.includes('not found') || err.message.includes('404')) {
        activeSessionId.value = null;
        messages.value = [];
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
      if (messages.value.length > 12) {
        isCompacting.value = true;
      }
      isChatLoading.value = true;
      errorMsg.value = null;
      // Add pessimistic message
      messages.value.push({ role: 'user', content: input });
      
      const res = await api.runPass(activeSessionId.value, input, activeAgent.value?.id);
      messages.value = res.state?.messages || [];
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

  const resetSession = async () => {
    if (!activeSessionId.value) return;
    try {
      const deletedId = activeSessionId.value; // 先记住要删的 id
      await api.resetSession(deletedId); // 调后端删除
      activeSessionId.value = null; // 清空当前选中，避免 watcher 试图加载已删 session
      messages.value = []; // 清空消息
      events.value = []; // 清空 trace
      await loadSessions(); // 刷新列表，删掉的 session 会消失
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
      messages.value = [];
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
    toggleSkill,
    
    // Mock Data
    availableAgents: MOCK_AGENTS
  };
}
