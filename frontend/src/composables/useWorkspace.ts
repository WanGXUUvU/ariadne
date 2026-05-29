import { computed, ref, watch } from 'vue';

import { api } from '../api/client';
import type {
  AgentMessage,
  ApprovalInfo,
  ChildAgentInfo,
  CompactResponse,
  SessionSummary,
  StreamingItem,
  TraceRunSummary,
} from '../types';
import type { ViewMode } from '../types/ui';
import { useApprovalFlow } from './workspace/useApprovalFlow';
import { useChildAgentTracker } from './workspace/useChildAgentTracker';
import { useWorkspaceResources } from './workspace/useWorkspaceResources';
import { useRunStreaming } from './workspace/useRunStreaming';
import { useSessionState } from './workspace/useSessionState';
import { useWorkspaceCatalog } from './workspace/useWorkspaceCatalog';

export function useWorkspace() {
  const activeView = ref<ViewMode>('chat');

  const sessions = ref<SessionSummary[]>([]);
  const activeSessionId = ref<string | null>(null);
  const historyMessages = ref<AgentMessage[]>([]);
  const currentMessages = ref<AgentMessage[]>([]);
  const traceRuns = ref<TraceRunSummary[]>([]);

  const isInitializing = ref(true);
  const isChatLoading = ref(false);
  const isTraceLoading = ref(false);
  const isCompacting = ref(false);
  const isStreaming = ref(false);
  const streamingTimeline = ref<StreamingItem[]>([]);
  const lastCompletedRun = ref<TraceRunSummary | null>(null);
  const errorMsg = ref<string | null>(null);
  const infoMsg = ref<string | null>(null);

  const isAwaitingApproval = ref(false);
  const pendingApprovalInfo = ref<ApprovalInfo | null>(null);
  const permissionProfile = ref<string>('conservative');

  const streamAbortController = ref<AbortController | null>(null);
  const pendingRunId = ref<string | null>(null);
  const pendingUserInput = ref<string>('');
  const pendingAgentName = ref<string | undefined>(undefined);

  const { childAgentsBySession, onLiveAgentEvent, extractChildAgents, clearChildAgents } = useChildAgentTracker();
  const { workspaces, isWorkspacesLoading, loadWorkspaces, selectWorkspaceDialog } = useWorkspaceCatalog(errorMsg);
  const resources = useWorkspaceResources({ activeSessionId, errorMsg });

  const sessionState = useSessionState({
    sessions,
    activeSessionId,
    historyMessages,
    currentMessages,
    traceRuns,
    isChatLoading,
    isTraceLoading,
    errorMsg,
    permissionProfile,
    modelId: resources.modelId,
    modelProviderId: resources.modelProviderId,
    thinkingEnabled: resources.thinkingEnabled,
    thinkingEffort: resources.thinkingEffort,
    childAgentsBySession,
    extractChildAgents,
    clearChildAgents,
  });

  const messages = computed(() => [...historyMessages.value, ...currentMessages.value]);
  const activeSession = computed(() =>
    sessions.value.find((session) => session.session_id === activeSessionId.value) ?? null,
  );

  const updatePermissionProfile = async (profile: string) => {
    if (!activeSessionId.value) return;
    permissionProfile.value = profile;
    try {
      await api.updateSessionProfile(activeSessionId.value, profile);
    } catch (err: any) {
      errorMsg.value = 'Failed to update profile: ' + err.message;
    }
  };

  const runStreaming = useRunStreaming({
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
    activeAgent: resources.activeAgent,
    pendingRunId,
    pendingUserInput,
    pendingAgentName,
    streamAbortController,
    onLiveAgentEvent,
    extractChildAgents,
  });

  const approvalFlow = useApprovalFlow({
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
  });

  const compactSession = async () => {
    if (!activeSessionId.value) return;
    try {
      isCompacting.value = true;
      errorMsg.value = null;
      const result: CompactResponse = await api.compactSession(activeSessionId.value);
      await sessionState.loadSessionDetail(activeSessionId.value);
      await sessionState.loadSessions(activeSessionId.value);
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

  const initializeWorkspace = async () => {
    isInitializing.value = true;
    await Promise.all([
      sessionState.loadSessions(),
      resources.loadSkills(),
      resources.fetchAgents(),
      resources.loadEnabledModels(),
      loadWorkspaces(),
    ]);
    isInitializing.value = false;
  };

  watch(activeSessionId, (newId) => {
    if (isStreaming.value || isChatLoading.value) return;
    if (newId) {
      sessionState.loadSessionDetail(newId);
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
    skills: resources.skills,
    activeAgentId: resources.activeAgentId,
    activeAgent: resources.activeAgent,
    isInitializing,
    isChatLoading,
    isTraceLoading,
    isSkillsLoading: resources.isSkillsLoading,
    isCompacting,
    isStreaming,
    streamingTimeline,
    lastCompletedRun,
    errorMsg,
    infoMsg,
    isAwaitingApproval,
    pendingApprovalInfo,
    permissionProfile,
    childAgentsBySession,
    api,
    initializeWorkspace,
    createNewSession: sessionState.createNewSession,
    sendMessage: runStreaming.sendMessage,
    stopStreaming: runStreaming.stopStreaming,
    approveAction: approvalFlow.approveAction,
    rejectAction: approvalFlow.rejectAction,
    approveAllAction: approvalFlow.approveAllAction,
    updatePermissionProfile,
    compactSession,
    resetSession: sessionState.resetSession,
    deleteSession: sessionState.deleteSession,
    renameSession: sessionState.renameSession,
    toggleSkill: resources.toggleSkill,
    availableAgents: resources.availableAgents,
    customAgents: computed(() => resources.availableAgents.value.filter(agent => !agent.is_builtin)),
    saveAgent: resources.saveAgent,
    deleteAgent: resources.deleteAgent,
    modelId: resources.modelId,
    modelProviderId: resources.modelProviderId,
    thinkingEnabled: resources.thinkingEnabled,
    thinkingEffort: resources.thinkingEffort,
    updateModelConfig: resources.updateModelConfig,
    enabledModels: resources.enabledModels,
    loadEnabledModels: resources.loadEnabledModels,
    activeModelContextLength: resources.activeModelContextLength,
    settingsApi: resources.settingsApi,
    workspaces,
    isWorkspacesLoading,
    loadWorkspaces,
    selectWorkspaceDialog,
  };
}
