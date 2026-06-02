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
import { extractPendingApprovalsFromTraceRuns } from '../utils/approvalQueue';
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
  const streamingPrefixTimeline = ref<StreamingItem[]>([]); // 审批流式前缀：initialTimeline，供 streaming block 合并渲染
  const lastCompletedRun = ref<TraceRunSummary | null>(null);
  const errorMsg = ref<string | null>(null);
  const infoMsg = ref<string | null>(null);

  const isAwaitingApproval = ref(false);
  const pendingApprovalInfo = ref<ApprovalInfo | null>(null);
  const pendingApprovalInfos = ref<ApprovalInfo[]>([]);
  const isResolvingApproval = ref(false);
  const permissionProfile = ref<string>('conservative');

  const streamAbortController = ref<AbortController | null>(null);
  const pendingRunId = ref<string | null>(null);
  const pendingUserInput = ref<string>('');
  const pendingAgentName = ref<string | undefined>(undefined);
  const pendingSkillName = ref<string | null>(null);

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
    pendingApprovalInfos,
    activeAgent: resources.activeAgent,
    pendingRunId,
    pendingUserInput,
    pendingAgentName,
    pendingSkillName,
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
    streamingPrefixTimeline,
    lastCompletedRun,
    errorMsg,
    isAwaitingApproval,
    pendingApprovalInfo,
    pendingApprovalInfos,
    isResolvingApproval,
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

  watch(traceRuns, (newRuns) => {
    if (isStreaming.value || isResolvingApproval.value) return;

    const pendingApprovals = extractPendingApprovalsFromTraceRuns(newRuns ?? []);

    if (pendingApprovals.length > 0) {
      isAwaitingApproval.value = true;
      pendingApprovalInfos.value = pendingApprovals;
      pendingApprovalInfo.value = pendingApprovals[0];
    } else {
      // ⚠️ 只有当前确实不在等待审批状态时，才清空 pendingApprovalInfo
      // 避免 stream 结束后 isStreaming = false 触发 watcher，而 traceRuns 尚未回填导致误清空
      if (!isAwaitingApproval.value) {
        pendingApprovalInfos.value = [];
        pendingApprovalInfo.value = null;
      }
    }
  }, { deep: true, immediate: true });

  const retryLastRun = () => {
    if (pendingUserInput.value) {
      runStreaming.sendMessage(pendingUserInput.value, pendingSkillName.value);
    }
  };

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
    streamingPrefixTimeline,
    lastCompletedRun,
    errorMsg,
    infoMsg,
    isAwaitingApproval,
    pendingApprovalInfo,
    pendingApprovalInfos,
    isResolvingApproval,
    permissionProfile,
    childAgentsBySession,
    api,
    initializeWorkspace,
    createNewSession: sessionState.createNewSession,
    sendMessage: runStreaming.sendMessage,
    retryLastRun,
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
