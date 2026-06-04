import { type Ref } from 'vue';

import { api } from '../../api/client';
import type {
  AgentMessage,
  ChildAgentInfo,
  SessionSummary,
  TraceResponse,
  TraceRunSummary,
} from '../../types';
import {
  clearSessionResetHistory,
  reconstructUiMessages,
  RESET_MARKER_CONTENT,
  readSessionResetHistory,
  writeSessionResetHistory,
} from './helpers';

type ExtractChildAgents = (sessionId: string, msgs: AgentMessage[], traceRuns: TraceRunSummary[]) => void;
type ClearChildAgents = (sessionId: string) => void;

interface SessionStateOptions {
  sessions: Ref<SessionSummary[]>;
  activeSessionId: Ref<string | null>;
  historyMessages: Ref<AgentMessage[]>;
  currentMessages: Ref<AgentMessage[]>;
  traceRuns: Ref<TraceRunSummary[]>;
  isChatLoading: Ref<boolean>;
  isTraceLoading: Ref<boolean>;
  errorMsg: Ref<string | null>;
  permissionProfile: Ref<string>;
  modelId: Ref<string | null>;
  modelProviderId: Ref<number | null>;
  thinkingEnabled: Ref<boolean>;
  thinkingEffort: Ref<string>;
  childAgentsBySession: Ref<Record<string, ChildAgentInfo[]>>;
  extractChildAgents: ExtractChildAgents;
  clearChildAgents: ClearChildAgents;
}

export function useSessionState(options: SessionStateOptions) {
  const {
    sessions,
    activeSessionId,
    historyMessages,
    currentMessages,
    traceRuns,
    isChatLoading,
    isTraceLoading,
    errorMsg,
    permissionProfile,
    modelId,
    modelProviderId,
    thinkingEnabled,
    thinkingEffort,
    childAgentsBySession,
    extractChildAgents,
    clearChildAgents,
  } = options;

  const loadSessions = async (preferredSessionId?: string | null) => {
    try {
      const data = await api.getSessions();
      sessions.value = data || [];
      if (preferredSessionId) {
        const matched = sessions.value.find(session => session.session_id === preferredSessionId);
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
      if (activeSessionId.value === sessionId) {
        traceRuns.value = trace.runs || [];
      }
    } catch {
      if (activeSessionId.value === sessionId) {
        traceRuns.value = [];
      }
    } finally {
      if (activeSessionId.value === sessionId) {
        isTraceLoading.value = false;
      }
    }
  };

  const loadSessionDetail = async (id: string) => {
    try {
      isChatLoading.value = true;
      isTraceLoading.value = true;
      
      const [detail, trace] = await Promise.all([
        api.getSessionDetail(id),
        api.getTrace(id).catch(() => ({ runs: [] })),
      ]);

      if (activeSessionId.value === id) {
        historyMessages.value = readSessionResetHistory(id);
        traceRuns.value = trace.runs || [];
        const msgs = detail.state?.messages || [];
        currentMessages.value = reconstructUiMessages(traceRuns.value, msgs);
        extractChildAgents(id, currentMessages.value, traceRuns.value);
        permissionProfile.value = detail.permission_profile ?? 'conservative';
        modelId.value = (detail as any).model_id ?? null;
        modelProviderId.value = (detail as any).model_provider_id ?? null;
        thinkingEnabled.value = (detail as any).thinking_enabled ?? false;
        thinkingEffort.value = (detail as any).thinking_effort ?? 'medium';
        if (detail.workspace_path && detail.workspace_exists === false) {
          errorMsg.value =
            `当前会话绑定的工作区目录已不存在：${detail.workspace_path}。请重新绑定文件夹后再继续。`;
        } else {
          errorMsg.value = null;
        }
      }
    } catch (err: any) {
      if (activeSessionId.value === id) {
        if (err.message.includes('not found') || err.message.includes('404')) {
          activeSessionId.value = null;
          historyMessages.value = [];
          currentMessages.value = [];
          traceRuns.value = [];
        } else {
          errorMsg.value = 'Failed to load session details: ' + err.message;
        }
      }
    } finally {
      if (activeSessionId.value === id) {
        isChatLoading.value = false;
        isTraceLoading.value = false;
      }
    }
  };

  const createNewSession = async (
    workspacePath?: string | null,
    workspaceName?: string | null,
    sessionName?: string,
    sessionType: string = 'coding',
  ) => {
    try {
      isChatLoading.value = true;
      const newSession = await api.createSession(workspacePath, workspaceName, sessionName, sessionType);
      await loadSessions(newSession.session_id);
      historyMessages.value = [];
      currentMessages.value = [];
      traceRuns.value = [];
      errorMsg.value = null;
    } catch (err: any) {
      errorMsg.value = 'Failed to create session: ' + err.message;
      return;
    } finally {
      isChatLoading.value = false;
    }
    if (activeSessionId.value) {
      await loadSessionDetail(activeSessionId.value);
    }
  };

  const deleteSession = async (id: string) => {
    try {
      await api.deleteSession(id);
      clearSessionResetHistory(id);
      clearChildAgents(id);
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
      delete childAgentsBySession.value[currentId];
      await loadSessions(currentId);
    } catch (err: any) {
      errorMsg.value = 'Reset failed: ' + err.message;
    }
  };

  return {
    loadSessions,
    loadTraceRuns,
    loadSessionDetail,
    createNewSession,
    deleteSession,
    renameSession,
    resetSession,
  };
}
