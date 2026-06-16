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
  interruptionPendingMessage: string | null;
  interruptionPendingSkill: string | null;
  interruptionWaitForTool: boolean;
}

const createDefaultSessionState = (): SessionSpecificState => ({
  historyMessages: [],
  currentMessages: [],
  traceRuns: [],
  isChatLoading: false,
  isTraceLoading: false,
  isStreaming: false,
  streamingTimeline: [],
  streamingPrefixTimeline: [],
  lastCompletedRun: null,
  errorMsg: null,
  isAwaitingApproval: false,
  pendingApprovalInfo: null,
  pendingApprovalInfos: [],
  permissionProfile: 'conservative',
  streamAbortController: null,
  pendingRunId: null,
  pendingUserInput: '',
  pendingAgentName: undefined,
  pendingSkillName: null,
  interruptionPendingMessage: null,
  interruptionPendingSkill: null,
  interruptionWaitForTool: false,
});

export function useWorkspace() {
  const activeView = ref<ViewMode>('chat');

  const sessions = ref<SessionSummary[]>([]);
  const activeSessionId = ref<string | null>(null);

  const sessionStates = ref<Record<string, SessionSpecificState>>({});

  const getSessionState = (sessionId: string): SessionSpecificState => {
    if (!sessionStates.value[sessionId]) {
      sessionStates.value[sessionId] = createDefaultSessionState();
    }
    return sessionStates.value[sessionId];
  };

  const historyMessages = computed({
    get: () => activeSessionId.value ? getSessionState(activeSessionId.value).historyMessages : [],
    set: (val) => { if (activeSessionId.value) getSessionState(activeSessionId.value).historyMessages = val; }
  });

  const currentMessages = computed({
    get: () => activeSessionId.value ? getSessionState(activeSessionId.value).currentMessages : [],
    set: (val) => { if (activeSessionId.value) getSessionState(activeSessionId.value).currentMessages = val; }
  });

  const traceRuns = computed({
    get: () => activeSessionId.value ? getSessionState(activeSessionId.value).traceRuns : [],
    set: (val) => { if (activeSessionId.value) getSessionState(activeSessionId.value).traceRuns = val; }
  });

  const isInitializing = ref(true);

  const isChatLoading = computed({
    get: () => activeSessionId.value ? getSessionState(activeSessionId.value).isChatLoading : false,
    set: (val) => { if (activeSessionId.value) getSessionState(activeSessionId.value).isChatLoading = val; }
  });

  const isTraceLoading = computed({
    get: () => activeSessionId.value ? getSessionState(activeSessionId.value).isTraceLoading : false,
    set: (val) => { if (activeSessionId.value) getSessionState(activeSessionId.value).isTraceLoading = val; }
  });

  const isCompacting = ref(false);

  const isStreaming = computed({
    get: () => activeSessionId.value ? getSessionState(activeSessionId.value).isStreaming : false,
    set: (val) => { if (activeSessionId.value) getSessionState(activeSessionId.value).isStreaming = val; }
  });

  const streamingTimeline = computed({
    get: () => activeSessionId.value ? getSessionState(activeSessionId.value).streamingTimeline : [],
    set: (val) => { if (activeSessionId.value) getSessionState(activeSessionId.value).streamingTimeline = val; }
  });

  const streamingPrefixTimeline = computed({
    get: () => activeSessionId.value ? getSessionState(activeSessionId.value).streamingPrefixTimeline : [],
    set: (val) => { if (activeSessionId.value) getSessionState(activeSessionId.value).streamingPrefixTimeline = val; }
  });

  const interruptionPendingMessage = computed({
    get: () => activeSessionId.value ? getSessionState(activeSessionId.value).interruptionPendingMessage : null,
    set: (val) => { if (activeSessionId.value) getSessionState(activeSessionId.value).interruptionPendingMessage = val; }
  });

  const interruptionWaitForTool = computed({
    get: () => activeSessionId.value ? getSessionState(activeSessionId.value).interruptionWaitForTool : false,
    set: (val) => { if (activeSessionId.value) getSessionState(activeSessionId.value).interruptionWaitForTool = val; }
  });

  const isToolRunning = computed(() => {
    if (!activeSessionId.value) return false;
    const state = getSessionState(activeSessionId.value);
    if (!state.isStreaming) return false;

    let activeToolCallsCount = 0;
    for (const item of state.streamingTimeline) {
      if (item.kind === 'event') {
        if (item.event.type === 'assistant_tool_call') {
          activeToolCallsCount++;
        } else if (item.event.type === 'tool_result' || item.event.type === 'tool_error') {
          activeToolCallsCount--;
        }
      }
    }
    return activeToolCallsCount > 0;
  });

  const lastCompletedRun = computed({
    get: () => activeSessionId.value ? getSessionState(activeSessionId.value).lastCompletedRun : null,
    set: (val) => { if (activeSessionId.value) getSessionState(activeSessionId.value).lastCompletedRun = val; }
  });

  const errorMsg = computed({
    get: () => activeSessionId.value ? getSessionState(activeSessionId.value).errorMsg : null,
    set: (val) => { if (activeSessionId.value) getSessionState(activeSessionId.value).errorMsg = val; }
  });

  const infoMsg = ref<string | null>(null);

  const isAwaitingApproval = computed({
    get: () => activeSessionId.value ? getSessionState(activeSessionId.value).isAwaitingApproval : false,
    set: (val) => { if (activeSessionId.value) getSessionState(activeSessionId.value).isAwaitingApproval = val; }
  });

  const pendingApprovalInfo = computed({
    get: () => activeSessionId.value ? getSessionState(activeSessionId.value).pendingApprovalInfo : null,
    set: (val) => { if (activeSessionId.value) getSessionState(activeSessionId.value).pendingApprovalInfo = val; }
  });

  const pendingApprovalInfos = computed({
    get: () => activeSessionId.value ? getSessionState(activeSessionId.value).pendingApprovalInfos : [],
    set: (val) => { if (activeSessionId.value) getSessionState(activeSessionId.value).pendingApprovalInfos = val; }
  });

  const isResolvingApproval = ref(false);

  const permissionProfile = computed({
    get: () => activeSessionId.value ? getSessionState(activeSessionId.value).permissionProfile : 'conservative',
    set: (val) => { if (activeSessionId.value) getSessionState(activeSessionId.value).permissionProfile = val; }
  });

  const streamAbortController = computed({
    get: () => activeSessionId.value ? getSessionState(activeSessionId.value).streamAbortController : null,
    set: (val) => { if (activeSessionId.value) getSessionState(activeSessionId.value).streamAbortController = val; }
  });

  const pendingRunId = computed({
    get: () => activeSessionId.value ? getSessionState(activeSessionId.value).pendingRunId : null,
    set: (val) => { if (activeSessionId.value) getSessionState(activeSessionId.value).pendingRunId = val; }
  });

  const pendingUserInput = computed({
    get: () => activeSessionId.value ? getSessionState(activeSessionId.value).pendingUserInput : '',
    set: (val) => { if (activeSessionId.value) getSessionState(activeSessionId.value).pendingUserInput = val; }
  });

  const pendingAgentName = computed({
    get: () => activeSessionId.value ? getSessionState(activeSessionId.value).pendingAgentName : undefined,
    set: (val) => { if (activeSessionId.value) getSessionState(activeSessionId.value).pendingAgentName = val; }
  });

  const pendingSkillName = computed({
    get: () => activeSessionId.value ? getSessionState(activeSessionId.value).pendingSkillName : null,
    set: (val) => { if (activeSessionId.value) getSessionState(activeSessionId.value).pendingSkillName = val; }
  });

  const { childAgentsBySession, onLiveRunEvent, extractChildAgents, clearChildAgents } = useChildAgentTracker();
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
    getSessionState,
    activeAgent: resources.activeAgent,
    onLiveRunEvent,
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
    onLiveRunEvent,
    extractChildAgents,
    updatePermissionProfile,
  });

  const compactSession = async () => {
    if (!activeSessionId.value) return;
    const targetSessionId = activeSessionId.value;
    try {
      isCompacting.value = true;
      // errorMsg is now a computed property with setter
      errorMsg.value = null;
      const result: CompactResponse = await api.compactSession(targetSessionId);
      if (activeSessionId.value === targetSessionId) {
        await sessionState.loadSessionDetail(targetSessionId);
        await sessionState.loadSessions(targetSessionId);
        if (result?.did_compact === false) {
          infoMsg.value = '✓ Context is already up to date — no compaction needed.';
        } else {
          infoMsg.value = `✓ Context compacted. ${result?.removed_count ?? ''} messages summarized.`;
        }
        setTimeout(() => {
          infoMsg.value = null;
        }, 3000);
      }
    } catch (err: any) {
      if (activeSessionId.value === targetSessionId) {
        errorMsg.value = 'Compact failed: ' + err.message;
      }
    } finally {
      if (activeSessionId.value === targetSessionId) {
        isCompacting.value = false;
      }
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
    if (newId) {
      const state = getSessionState(newId);
      if (!state.isStreaming) {
        sessionState.loadSessionDetail(newId);
      }
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

  const editAndReRun = async (messageIndex: number, newContent: string) => {
    if (!activeSessionId.value) return;
    const targetSessionId = activeSessionId.value;
    try {
      isChatLoading.value = true;
      errorMsg.value = null;
      await api.truncateSession(targetSessionId, messageIndex);
      if (activeSessionId.value === targetSessionId) {
        await sessionState.loadSessionDetail(targetSessionId);
        await sessionState.loadSessions(targetSessionId);
        await runStreaming.sendMessage(newContent, null);
      }
    } catch (err: any) {
      if (activeSessionId.value === targetSessionId) {
        errorMsg.value = 'Failed to edit message: ' + err.message;
      }
    } finally {
      if (activeSessionId.value === targetSessionId) {
        isChatLoading.value = false;
      }
    }
  };

  const forceInterruptAndSend = async () => {
    if (!activeSessionId.value) return;
    const state = getSessionState(activeSessionId.value);
    const msg = state.interruptionPendingMessage;
    const skill = state.interruptionPendingSkill;

    state.interruptionPendingMessage = null;
    state.interruptionPendingSkill = null;
    state.interruptionWaitForTool = false;

    await runStreaming.stopStreaming();
    if (msg) {
      await sendMessage(msg, skill);
    }
  };

  const withdrawInterruption = () => {
    if (!activeSessionId.value) return null;
    const state = getSessionState(activeSessionId.value);
    const msg = state.interruptionPendingMessage;

    state.interruptionPendingMessage = null;
    state.interruptionPendingSkill = null;
    state.interruptionWaitForTool = false;

    return msg;
  };

  const discardInterruption = () => {
    if (!activeSessionId.value) return;
    const state = getSessionState(activeSessionId.value);
    state.interruptionPendingMessage = null;
    state.interruptionPendingSkill = null;
    state.interruptionWaitForTool = false;
  };

  const sendMessage = async (input: string, skillName?: string | null) => {
    const trimmed = input.trim();
    if (!trimmed) return;

    if (isStreaming.value) {
      const targetSessionId = activeSessionId.value;
      if (targetSessionId) {
        const state = getSessionState(targetSessionId);
        let activeToolCallsCount = 0;
        for (const item of state.streamingTimeline) {
          if (item.kind === 'event') {
            if (item.event.type === 'assistant_tool_call') {
              activeToolCallsCount++;
            } else if (item.event.type === 'tool_result' || item.event.type === 'tool_error') {
              activeToolCallsCount--;
            }
          }
        }
        if (activeToolCallsCount > 0) {
          state.interruptionPendingMessage = trimmed;
          state.interruptionPendingSkill = skillName ?? null;
          state.interruptionWaitForTool = true; // 默认自动排队等待
          return;
        }
      }

      // 如果当前没有运行的工具，直接瞬间打断
      await runStreaming.stopStreaming();
    }

    if (trimmed === '/fork' || trimmed.startsWith('/fork ')) {
      if (!activeSessionId.value) return;

      const parentName = activeSession.value?.session_name || 'Untitled';
      // 计算在新会话中的命名，例如 fork: 开发周报
      const forkName = `fork: ${parentName}`;
      const targetSessionId = activeSessionId.value;

      let newPrompt: string | null = null;
      if (trimmed.startsWith('/fork ')) {
        newPrompt = trimmed.substring(6).trim();
      }

      // 我们需要在原会话的末尾位置进行克隆所有消息
      const messageIndex = messages.value.length;

      try {
        isChatLoading.value = true;
        errorMsg.value = null;

        // 调用后端克隆接口
        const newSession = await api.forkSession(targetSessionId, messageIndex);

        if (activeSessionId.value === targetSessionId) {
          // 重载会话列表
          await sessionState.loadSessions(newSession.session_id);
          // 切换到新派生分支会话
          activeSessionId.value = newSession.session_id;

          // 重读会话细节以完成渲染
          await sessionState.loadSessionDetail(newSession.session_id);

          // 如果有附加新提示词，在新会话里自动发送
          if (newPrompt && newPrompt !== '') {
            setTimeout(() => {
              runStreaming.sendMessage(newPrompt!, null);
            }, 100);
          }
        }
      } catch (err: any) {
        if (activeSessionId.value === targetSessionId) {
          errorMsg.value = 'Failed to fork session: ' + err.message;
        }
      } finally {
        if (activeSessionId.value === targetSessionId) {
          isChatLoading.value = false;
        }
      }
      return;
    }

    // 正常发送消息
    await runStreaming.sendMessage(input, skillName);
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
    sendMessage,
    retryLastRun,
    editAndReRun,
    stopStreaming: runStreaming.stopStreaming,
    interruptionPendingMessage,
    interruptionWaitForTool,
    isToolRunning,
    forceInterruptAndSend,
    withdrawInterruption,
    discardInterruption,
    approveAction: approvalFlow.approveAction,
    rejectAction: approvalFlow.rejectAction,
    approveAllAction: approvalFlow.approveAllAction,
    updatePermissionProfile,
    compactSession,
    resetSession: sessionState.resetSession,
    deleteSession: sessionState.deleteSession,
    renameSession: sessionState.renameSession,
    toggleSkill: resources.toggleSkill,
    loadSkills: resources.loadSkills,
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
