import type { RunResponse, SessionDetail, SessionSummary, AgentEvent, SkillMetadata, TraceResponse, CompactResponse } from '../types';

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

export const api = {
  getSessions: () => fetchApi<SessionSummary[]>('/sessions'),
  createSession: () =>
    fetchApi<SessionSummary>('/sessions', {
      method: 'POST',
      body: JSON.stringify({}),
    }),
  getSessionDetail: (id: string) => fetchApi<SessionDetail>(`/sessions/${id}`),
  runPass: (session_id: string, user_input: string, agent_name?: string) => 
    fetchApi<RunResponse>('/run', {
      method: 'POST',
      body: JSON.stringify({ session_id, user_input, agent_name }),
    }),
  getTrace: (session_id: string) => fetchApi<TraceResponse>(`/sessions/${session_id}/trace`),
  getSkills: () => fetchApi<SkillMetadata[]>('/skills'),
  enableSkill: (skill_name: string) => fetchApi<SkillMetadata>(`/skills/${skill_name}/enable`, { method: 'POST' }),
  disableSkill: (skill_name: string) => fetchApi<SkillMetadata>(`/skills/${skill_name}/disable`, { method: 'POST' }),
  compactSession: (session_id: string) => fetchApi<CompactResponse>(`/compact`, { method: 'POST', body: JSON.stringify({ session_id, trigger_threshold: 1 }) }), // 手动 compact 传 trigger_threshold:1，跳过默认 12 条阈值，确保任何时候都能触发
  resetSession: (session_id: string) => fetchApi<{ok: boolean}>(`/reset`, { method: 'POST', body: JSON.stringify({ session_id }) })
};
