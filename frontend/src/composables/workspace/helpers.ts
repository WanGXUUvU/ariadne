import type { RunEvent, AgentMessage, StreamingItem, TraceRunSummary } from '../../types';

const RESET_HISTORY_STORAGE_KEY = 'agent-build-reset-history-v1';
const TIMELINE_STORAGE_KEY = 'agent-build-timelines-v1';
export const RESET_MARKER_CONTENT = '[RESET_MARKER]';

type ResetHistoryStore = Record<string, AgentMessage[]>;
type TimelineStore = Record<string, StreamingItem[]>;

export function readTimelineStore(): TimelineStore {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(TIMELINE_STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw) as TimelineStore;
  } catch {
    return {};
  }
}

export function writeTimelineToStore(runId: string, timeline: StreamingItem[]) {
  if (typeof window === 'undefined') return;
  const store = readTimelineStore();
  store[runId] = timeline;
  const keys = Object.keys(store);
  if (keys.length > 50) {
    delete store[keys[0]];
  }
  window.localStorage.setItem(TIMELINE_STORAGE_KEY, JSON.stringify(store));
}

function readResetHistoryStore(): ResetHistoryStore {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(RESET_HISTORY_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== "object") return {};
    return parsed as ResetHistoryStore;
  } catch {
    return {};
  }
}

function writeResetHistoryStore(store: ResetHistoryStore) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(RESET_HISTORY_STORAGE_KEY, JSON.stringify(store));
}

export function readSessionResetHistory(sessionId: string): AgentMessage[] {
  return readResetHistoryStore()[sessionId] ?? [];
}

export function writeSessionResetHistory(sessionId: string, messages: AgentMessage[]) {
  const store = readResetHistoryStore();
  if (messages.length === 0) {
    delete store[sessionId];
  } else {
    store[sessionId] = messages;
  }
  writeResetHistoryStore(store);
}

export function clearSessionResetHistory(sessionId: string) {
  const store = readResetHistoryStore();
  if (!(sessionId in store)) return;
  delete store[sessionId];
  writeResetHistoryStore(store);
}

export function reconstructTimelineFromEvents(events: RunEvent[], reply?: string | null): StreamingItem[] {
  const timeline: StreamingItem[] = [];
  let hasText = false;
  for (const e of events) {
    if (e.type === 'thinking') {
      if (e.content) timeline.push({ kind: 'thinking', content: e.content });
    } else if (e.type === 'final_answer') {
      if (e.content) {
        timeline.push({ kind: 'text', content: e.content });
        hasText = true;
      }
    } else {
      timeline.push({ kind: 'event', event: e });
    }
  }
  if (!hasText && reply) {
    timeline.push({ kind: 'text', content: reply });
  }
  return timeline;
}

export function reconstructUiMessages(
  traceRuns: TraceRunSummary[],
  stateMessages: AgentMessage[],
): AgentMessage[] {
  const mainRuns = traceRuns.filter(r => !r.parent_run_id);
  const summaryMsg = stateMessages.find(
    m => m.role === 'system' && m.content?.includes('[COMPACT_SUMMARY]'),
  );
  const summaryText = (summaryMsg && summaryMsg.content)
    ? summaryMsg.content.replace('[COMPACT_SUMMARY]', '').trim()
    : '';

  const uiMessages: AgentMessage[] = [];
  mainRuns.forEach((run) => {
    const isActive = run.is_active !== 0;
    uiMessages.push({
      role: 'user',
      content: run.user_input,
      run_id: run.run_id,
      isActive,
      summary_text: summaryText,
    } as AgentMessage);
    uiMessages.push({
      role: 'assistant',
      content: run.reply,
      run_id: run.run_id,
      isActive,
      timeline: reconstructTimelineFromEvents(run.events, run.reply),
      summary_text: summaryText,
    } as AgentMessage);
  });
  return uiMessages;
}
