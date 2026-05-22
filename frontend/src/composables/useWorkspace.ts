import { ref, computed, watch } from 'vue';
import { api } from '../api/client';
import { settingsApi, type ModelSetting } from '../api/settings';
import type {
  SessionSummary,
  AgentMessage,
  AgentEvent,
  SkillMetadata,
  CompactResponse,
  TraceResponse,
  TraceRunSummary,
  StreamingItem,
  ChildAgentInfo,
  ApprovalInfo,
} from '../types';
import type { ViewMode } from '../types/ui';
import type { UiAgentOption } from '../types/ui';

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
  // 超过 50 条时删掉最早插入的，防止 localStorage 无限增长
  const keys = Object.keys(store);
  if (keys.length > 50) {
    delete store[keys[0]];
  }
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

  const availableAgents = ref<UiAgentOption[]>([]);
  const activeAgentId = ref<string>('default');

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

  // 审批等待状态
  const isAwaitingApproval = ref(false);
  const pendingApprovalInfo = ref<ApprovalInfo | null>(null);
  // 当前 session 的权限档位（本地跟踪，从 session 读取或更新后同步）
  const permissionProfile = ref<string>('conservative');

  // 当前 session 的模型配置（model_id / thinking_enabled / thinking_effort）
  const modelId = ref<string | null>(null);
  const modelProviderId = ref<number | null>(null);
  const thinkingEnabled = ref<boolean>(false);
  const thinkingEffort = ref<string>('medium');

  const enabledModels = ref<ModelSetting[]>([]);
  const loadEnabledModels = async () => {
    try {
      enabledModels.value = await settingsApi.listEnabledModels();
    } catch {
      // 容错处理
    }
  };

  const activeModelContextLength = computed(() => {
    if (!modelId.value) return 128000;
    const currentModel = enabledModels.value.find((m) => m.model_id === modelId.value);
    return currentModel?.context_length ?? 128000;
  });

  // 子 Agent 追踪：key = session_id，value = 当前 session spawn 出的子 Agent 列表
  const childAgentsBySession = ref<Record<string, ChildAgentInfo[]>>({});
  let childPollTimer: ReturnType<typeof setInterval> | null = null;

  // 单个 agent_event 到达时，实时检测是否是 spawn_child_agent 的 tool_result
  function onLiveAgentEvent(sessionId: string, ev: AgentEvent) {
    if (ev.type !== 'tool_result' || ev.tool_name !== 'spawn_child_agent' || !ev.tool_result?.ok) return;
    const runId = ev.tool_result.content ?? '';
    const agentName = (ev.tool_result.metadata?.agent_name as string) ?? '子Agent';
    if (!runId) return;
    const existing = childAgentsBySession.value[sessionId] ?? [];
    if (existing.find(c => c.run_id === runId)) return; // 已有，跳过
    childAgentsBySession.value[sessionId] = [
      ...existing,
      { run_id: runId, agent_name: agentName, status: 'running', reply: null, error: null },
    ];
    startChildPolling();
  }

  // 从消息的 timeline 事件里解析 spawn_child_agent tool_result，提取子 Agent 信息
  function extractChildAgents(sessionId: string, msgs: AgentMessage[]) {
    const children: ChildAgentInfo[] = [];
    
    // 从消息中的 timeline 查找
    for (const msg of msgs) {
      if (!msg.timeline) continue;
      for (const item of msg.timeline) {
        if (item.kind !== 'event') continue;
        const ev = item.event;
        if (ev.type === 'tool_result' && ev.tool_name === 'spawn_child_agent' && ev.tool_result?.ok) {
          const runId = ev.tool_result.content ?? '';
          const agentName = (ev.tool_result.metadata?.agent_name as string) ?? '子Agent';
          if (runId && !children.find(c => c.run_id === runId)) {
            children.push({ run_id: runId, agent_name: agentName, status: 'running', reply: null, error: null });
          }
        }
      }
    }
    
    // 如果从 timeline 中没有找到，再从 traceRuns 中查找
    if (children.length === 0) {
      for (const run of traceRuns.value) {
        for (const event of run.events) {
          if (event.type === 'tool_result' && event.tool_name === 'spawn_child_agent' && event.tool_result?.ok) {
            const runId = event.tool_result.content ?? '';
            const agentName = (event.tool_result.metadata?.agent_name as string) ?? '子Agent';
            if (runId && !children.find(c => c.run_id === runId)) {
              // 从 traceRuns 恢复时，状态统一设为 running，轮询会拉取真实状态更新
              children.push({ run_id: runId, agent_name: agentName, status: 'running', reply: null, error: null });
            }
          }
        }
      }
    }
    
    if (children.length > 0) {
      childAgentsBySession.value[sessionId] = children;
      startChildPolling();
    }
  }

  function startChildPolling() {
    if (childPollTimer !== null) return;
    childPollTimer = setInterval(async () => {
      let anyRunning = false;
      for (const [sid, children] of Object.entries(childAgentsBySession.value)) {
        for (const child of children) {
          if (child.status === 'running') {
            anyRunning = true;
            try {
              const res = await api.getChildRunStatus(child.run_id);
              child.status = res.status as ChildAgentInfo['status'];
              child.reply = res.reply;
              child.error = res.error;
            } catch {
              // 网络错误不影响轮询
            }
          }
        }
        // Vue 响应式需要触发更新
        childAgentsBySession.value[sid] = [...children];
      }
      if (!anyRunning) {
        clearInterval(childPollTimer!);
        childPollTimer = null;
      }
    }, 2000);
  }

  const messages = computed(() => [...historyMessages.value, ...currentMessages.value]);
  const activeSession = computed(() =>
    sessions.value.find((session) => session.session_id === activeSessionId.value) ?? null
  );

  const activeAgent = computed(() =>
    availableAgents.value.find((a) => a.id === activeAgentId.value) ?? availableAgents.value[0] ?? null
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
      return;
    } finally {
      isChatLoading.value = false;
    }
    // watch(activeSessionId) 在 isChatLoading=true 时被跳过，新 session 的模型配置不会自动加载。
    // 在这里显式调用 loadSessionDetail，确保新 session 的 modelId 等字段从后端正确同步。
    if (activeSessionId.value) {
      await loadSessionDetail(activeSessionId.value);
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
      extractChildAgents(id, msgs);
      // 同步 permission_profile
      permissionProfile.value = detail.permission_profile ?? 'conservative';
      // 同步模型配置字段（后端 session 记录里存的选项）
      modelId.value = (detail as any).model_id ?? null;
      modelProviderId.value = (detail as any).model_provider_id ?? null;
      thinkingEnabled.value = (detail as any).thinking_enabled ?? false;
      thinkingEffort.value = (detail as any).thinking_effort ?? 'medium';
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
          // 工具事件直接追加（跳过 final_answer，那是文字回答的元数据）
          if (frame.data.type !== 'final_answer') {
            streamingTimeline.value = [...streamingTimeline.value, { kind: 'event', event: frame.data }];
          }
          // 提取 approval_required 事件，记录 approval_id 和 tool 信息
          if (frame.data.type === 'approval_required' && frame.data.content) {
            // content 字段存的是 approval_id
            const approvalId = frame.data.content;
            pendingApprovalInfo.value = {
              approval_id: approvalId,
              tool_name: frame.data.tool_name ?? '',
              arguments: '',  // 从后端 GET 获取，稍后填充
              run_id: capturedRunId ?? '',
            };
            // 异步获取完整的 arguments
            api.getApproval(approvalId).then(info => {
              if (pendingApprovalInfo.value?.approval_id === approvalId) {
                pendingApprovalInfo.value = { ...pendingApprovalInfo.value, arguments: info.arguments };
              }
            }).catch(() => {});
          }
          // 实时检测 spawn_child_agent，让侧边栏立即出现子 Agent
          if (activeSessionId.value) {
            onLiveAgentEvent(activeSessionId.value, frame.data);
          }
        } else if (frame.type === 'paused') {
          // Agent 因审批暂停
          isAwaitingApproval.value = true;
          // 冻结当前 streaming timeline 保留已输出内容
          const partialTimeline = [...streamingTimeline.value];
          if (capturedRunId) {
            writeTimelineToStore(capturedRunId, partialTimeline);
          }
          // 追加 assistant 消息（含已有内容）
          const partialText = partialTimeline
            .filter(i => i.kind === 'text').map(i => i.content).join('');
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
          // 解析新消息里的子 Agent 事件，触发轮询
          if (activeSessionId.value) {
            extractChildAgents(activeSessionId.value, newMsgs);
          }
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
      // 如果正在等待审批，保持 isStreaming=false 但不清空 approval 状态
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

  // 审批操作：通用 SSE 流处理
  async function _handleApprovalStream(streamFn: () => AsyncGenerator<any>) {
    if (!pendingApprovalInfo.value) return;

    // 捕获初始运行（assistant_tool_call + approval_required）的 timeline，后面合并进续跑结果
    const initialTimeline: StreamingItem[] = [];
    for (let i = currentMessages.value.length - 1; i >= 0; i--) {
      const m = currentMessages.value[i];
      if (m.role === 'assistant' && m.timeline && m.timeline.length > 0) {
        initialTimeline.push(...m.timeline);
        break;
      }
    }

    isStreaming.value = true;
    isChatLoading.value = true;
    streamingTimeline.value = [];
    errorMsg.value = null;
    let capturedRunId: string | null = null;

    try {
      for await (const frame of streamFn()) {
        if (frame.type === 'start' || frame.type === 'resume') {
          capturedRunId = frame.data.run_id;
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
          if (activeSessionId.value) {
            onLiveAgentEvent(activeSessionId.value, frame.data);
          }
        } else if (frame.type === 'end') {
          // 合并：初始运行的工具调用事件 + 续跑的工具结果/文字事件
          const frozenTimeline = [...initialTimeline, ...streamingTimeline.value];
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
          if (activeSessionId.value) {
            extractChildAgents(activeSessionId.value, newMsgs);
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
          }
        } else if (frame.type === 'error') {
          errorMsg.value = frame.data.message ?? 'Approval error';
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        errorMsg.value = 'Resume failed: ' + err.message;
      }
    } finally {
      isAwaitingApproval.value = false;
      pendingApprovalInfo.value = null;
      isStreaming.value = false;
      isChatLoading.value = false;
      streamingTimeline.value = [];
    }
  }

  const approveAction = async () => {
    if (!pendingApprovalInfo.value) return;
    const id = pendingApprovalInfo.value.approval_id;
    await _handleApprovalStream(() => api.streamApprove(id));
  };

  const rejectAction = async () => {
    if (!pendingApprovalInfo.value) return;
    const id = pendingApprovalInfo.value.approval_id;
    await _handleApprovalStream(() => api.streamReject(id));
  };

  const approveAllAction = async () => {
    if (!pendingApprovalInfo.value) return;
    const id = pendingApprovalInfo.value.approval_id;
    // 切换到全自动模式，同步更新本地状态和后端
    await updatePermissionProfile('full-auto');
    await _handleApprovalStream(() => api.streamApproveAll(id));
  };

  const updatePermissionProfile = async (profile: string) => {
    if (!activeSessionId.value) return;
    permissionProfile.value = profile;
    try {
      await api.updateSessionProfile(activeSessionId.value, profile);
    } catch (err: any) {
      errorMsg.value = 'Failed to update profile: ' + err.message;
    }
  };

  /**
   * 更新当前 session 的模型配置（model_id / thinking_enabled / thinking_effort）
   * 乐观更新本地状态后，PATCH 到后端 session 记录。
   */
  const updateModelConfig = async (config: {
    model_id?: string | null;
    model_provider_id?: number | null;
    thinking_enabled?: boolean;
    thinking_effort?: string;
  }) => {
    if (!activeSessionId.value) return;
    // 乐观更新本地
    if (config.model_id !== undefined) modelId.value = config.model_id;
    if (config.model_provider_id !== undefined) modelProviderId.value = config.model_provider_id;
    if (config.thinking_enabled !== undefined) thinkingEnabled.value = config.thinking_enabled;
    if (config.thinking_effort !== undefined) thinkingEffort.value = config.thinking_effort;
    try {
      await fetch(
        `${import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'}/sessions/${activeSessionId.value}`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(config),
        },
      );
    } catch (err: any) {
      errorMsg.value = 'Failed to update model config: ' + err.message;
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
      // 清掉该 session 的子 Agent 面板
      delete childAgentsBySession.value[id];
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

  const fetchAgents = async () => {
    try {
      const data = await api.getAgents();
      availableAgents.value = (data ?? []).map((a) => ({
        id: a.id,
        name: a.name,
        description: a.description ?? '',
        icon: '\ud83e\udd16',
        is_builtin: a.is_builtin,
      }));
      // 如果当前 activeAgentId 不在列表里，回落到第一个
      if (availableAgents.value.length > 0 && !availableAgents.value.find((a) => a.id === activeAgentId.value)) {
        activeAgentId.value = availableAgents.value[0].id;
      }
    } catch {
      // 加载失败时保持空列表，不阻塞其他初始化
    }
  };

  const saveAgent = async (definition: { id: string; name: string; description: string; system_prompt: string; tool_names: string[] | null }) => {
    await api.saveAgent(definition);
    await fetchAgents();
  };

  const deleteAgent = async (agent_id: string) => {
    await api.deleteAgent(agent_id);
    await fetchAgents();
    // 如果删的是当前选中的 agent，回退到 default
    if (activeAgentId.value === agent_id) {
      activeAgentId.value = 'default';
    }
  };

  const initializeWorkspace = async () => {
    isInitializing.value = true;
    await Promise.all([loadSessions(), loadSkills(), fetchAgents(), loadEnabledModels()]);
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
    isAwaitingApproval,
    pendingApprovalInfo,
    permissionProfile,
    childAgentsBySession,
    api,
    initializeWorkspace,
    createNewSession,
    sendMessage,
    stopStreaming,
    approveAction,
    rejectAction,
    approveAllAction,
    updatePermissionProfile,
    compactSession,
    resetSession,
    deleteSession,
    renameSession,
    toggleSkill,
    availableAgents,
    customAgents: computed(() => availableAgents.value.filter(a => !a.is_builtin)),
    saveAgent,
    deleteAgent,
    // 模型配置
    modelId,
    modelProviderId,
    thinkingEnabled,
    thinkingEffort,
    updateModelConfig,
    enabledModels,
    loadEnabledModels,
    activeModelContextLength,
    settingsApi,
  };
}
