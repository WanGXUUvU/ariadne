import type { RunResponse, SessionDetail, SessionSummary, SkillMetadata, TraceResponse, CompactResponse, StreamFrame, ApprovalInfo, WorkspaceSummary } from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data?.error?.message || data?.detail || 'API Request Failed');
  }
  if (data?.error) {
    throw new Error(data.error.message || 'Business Error');
  }
  return data;
}

// SSE streaming：逐帧 yield StreamFrame，调用方用 for await 消费
async function* streamRun(
  session_id: string,
  user_input: string,
  agent_name?: string,
  skill_name?: string | null,
  signal?: AbortSignal,
): AsyncGenerator<StreamFrame> {
  yield* streamSse(`${API_BASE}/run/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id, user_input, agent_name, skill_name: skill_name ?? undefined }),
    signal,
  });
}

// 审批操作 SSE 流（approve / reject / approve_all）
async function* streamApproval(
  approvalId: string,
  action: 'approve' | 'reject' | 'approve_all',
  signal?: AbortSignal,
): AsyncGenerator<StreamFrame> {
  yield* streamSse(`${API_BASE}/approvals/${approvalId}/${action}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
    signal,
  });
}

// 公共 SSE 帧读取器
async function* streamSse(url: string, init: RequestInit): AsyncGenerator<StreamFrame> {
  const res = await fetch(url, init);

  if (!res.ok || !res.body) {
    throw new Error(`Stream request failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    // SSE 每帧以 \n\n 结尾，切割后逐行处理
    const parts = buffer.split('\n\n');
    buffer = parts.pop() ?? '';   // 最后一段可能不完整，留到下次

    for (const part of parts) {
      for (const line of part.split('\n')) {
        if (!line.startsWith('data: ')) continue;
        const text = line.slice(6).trim();
        if (text === '[DONE]') return;
        try {
          yield JSON.parse(text) as StreamFrame;
        } catch { /* 跳过无法解析的行 */ }
      }
    }
  }
}

export const api = {
  getSessions: () => fetchApi<SessionSummary[]>('/sessions'),
  createSession: (workspace_path?: string | null, workspace_name?: string | null, session_name?: string, session_type?: string) =>
    fetchApi<SessionSummary>('/sessions', {
      method: 'POST',
      body: JSON.stringify({ workspace_path, workspace_name, session_name, session_type }),
    }),
  getWorkspaces: () => fetchApi<WorkspaceSummary[]>('/workspaces'),
  selectWorkspaceDialog: () => fetchApi<WorkspaceSummary>('/workspaces/select-dialog', { method: 'POST' }),
  getSessionDetail: (id: string) => fetchApi<SessionDetail>(`/sessions/${id}`),
  runPass: (session_id: string, user_input: string, agent_name?: string) => 
    fetchApi<RunResponse>('/run', {
      method: 'POST',
      body: JSON.stringify({ session_id, user_input, agent_name }),
    }),
  streamRun: (session_id: string, user_input: string, agent_name?: string, skill_name?: string | null, signal?: AbortSignal) =>
    streamRun(session_id, user_input, agent_name, skill_name, signal),
  finalizeRun: (
    session_id: string,
    run_id: string,
    user_input: string,
    partial_reply: string,
    agent_name?: string,
  ) =>
    fetchApi<{ ok: boolean }>(`/sessions/${session_id}/runs/${run_id}/finalize`, {
      method: 'POST',
      body: JSON.stringify({ user_input, partial_reply, agent_name }),
    }),
  getTrace: (session_id: string, run_id?: string) => {
    const url = run_id 
      ? `/sessions/${session_id}/trace?run_id=${encodeURIComponent(run_id)}`
      : `/sessions/${session_id}/trace`;
    return fetchApi<TraceResponse>(url);
  },
  getSkills: () => fetchApi<SkillMetadata[]>('/skills'),
  enableSkill: (skill_name: string) => fetchApi<SkillMetadata>(`/skills/${skill_name}/enable`, { method: 'POST' }),
  disableSkill: (skill_name: string) => fetchApi<SkillMetadata>(`/skills/${skill_name}/disable`, { method: 'POST' }),
  compactSession: (session_id: string) => fetchApi<CompactResponse>(`/compact`, { method: 'POST', body: JSON.stringify({ session_id, trigger_threshold: 1, force: true }) }), // 手动 compact 传 force:true，跳过 token 占用率阈值，确保任何时候都能触发
  resetSession: (session_id: string) => fetchApi<{ok: boolean}>(`/reset`, { method: 'POST', body: JSON.stringify({ session_id }) }),
  deleteSession: (session_id: string) => fetchApi<{ok: boolean}>(`/sessions/${session_id}`, { method: 'DELETE' }),
  renameSession: (session_id: string, session_name: string) => fetchApi<{ok: boolean}>(`/sessions/${session_id}`, { method: 'PATCH', body: JSON.stringify({ session_name }) }),
  patchSession: (
    session_id: string,
    patch: {
      session_name?: string;
      permission_profile?: string;
      model_id?: string | null;
      model_provider_id?: number | null;
      thinking_enabled?: boolean;
      thinking_effort?: string;
      workspace_path?: string | null;
      workspace_name?: string | null;
    },
  ) => fetchApi<{ ok: boolean }>(`/sessions/${session_id}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  }),
  getChildRunStatus: (run_id: string) => fetchApi<{ status: string; reply: string | null; error: string | null }>(`/child-runs/${run_id}`),
  getAgents: () => fetchApi<{ id: string; name: string; description: string | null; tool_names: string[] | null; is_builtin: boolean }[]>('/agents'),
  getTools: () => fetchApi<{ name: string }[]>('/tools'),
  saveAgent: (definition: { id: string; name: string; description: string | null; system_prompt: string; tool_names: string[] | null }) =>
    fetchApi<{ id: string; name: string; description: string | null; system_prompt: string; tool_names: string[] | null }>('/agents', {
      method: 'POST',
      body: JSON.stringify(definition),
    }),
  deleteAgent: (agent_id: string) => fetchApi<null>(`/agents/${agent_id}`, { method: 'DELETE' }),
  // 审批操作
  getApproval: (approval_id: string) => fetchApi<ApprovalInfo>(`/approvals/${approval_id}`),
  streamApprove: (approval_id: string, signal?: AbortSignal) => streamApproval(approval_id, 'approve', signal),
  streamReject: (approval_id: string, signal?: AbortSignal) => streamApproval(approval_id, 'reject', signal),
  streamApproveAll: (approval_id: string, signal?: AbortSignal) => streamApproval(approval_id, 'approve_all', signal),
  // 更新 session permission profile
  updateSessionProfile: (session_id: string, permission_profile: string) =>
    fetchApi<{ ok: boolean }>(`/sessions/${session_id}`, {
      method: 'PATCH',
      body: JSON.stringify({ permission_profile }),
    }),
  // 截断 session 历史
  truncateSession: (session_id: string, message_index: number) =>
    fetchApi<{ ok: boolean }>(`/sessions/${session_id}/truncate`, {
      method: 'POST',
      body: JSON.stringify({ message_index }),
    }),
  // 派生分支会话
  forkSession: (session_id: string, message_index: number) =>
    fetchApi<SessionSummary>(`/sessions/${session_id}/fork`, {
      method: 'POST',
      body: JSON.stringify({ message_index }),
    }),
};
