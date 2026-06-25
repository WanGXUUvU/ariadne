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

const MAX_STORE_ENTRIES = 50;
const MAX_TOOL_RESULT_LENGTH = 50_000; // 截断超大 tool_result content（~50KB）

function trimTimelineForStorage(timeline: StreamingItem[]): StreamingItem[] {
  return timeline.map(item => {
    if (item.kind !== 'event') return item;
    const ev = item.event;
    if (
      (ev.type === 'tool_result' || ev.type === 'tool_error') &&
      ev.tool_result?.content &&
      ev.tool_result.content.length > MAX_TOOL_RESULT_LENGTH
    ) {
      return {
        kind: 'event',
        event: {
          ...ev,
          tool_result: {
            ...ev.tool_result,
            content: ev.tool_result.content.slice(0, MAX_TOOL_RESULT_LENGTH) +
              `\n…[truncated ${ev.tool_result.content.length - MAX_TOOL_RESULT_LENGTH} chars for storage]`,
          },
        },
      };
    }
    return item;
  });
}

export function writeTimelineToStore(runId: string, timeline: StreamingItem[]) {
  if (typeof window === 'undefined') return;
  const store = readTimelineStore();
  store[runId] = trimTimelineForStorage(timeline);

  const keys = Object.keys(store);
  // 超过上限时先清理
  while (keys.length > MAX_STORE_ENTRIES) {
    delete store[keys.shift()!];
  }

  try {
    window.localStorage.setItem(TIMELINE_STORAGE_KEY, JSON.stringify(store));
  } catch (e: unknown) {
    // QuotaExceededError — 主动腾出空间后重试
    if (e instanceof DOMException && e.name === 'QuotaExceededError') {
      const remainingKeys = Object.keys(store);
      // 激进腾出：只保留最近 10 条
      while (remainingKeys.length > 10) {
        delete store[remainingKeys.shift()!];
      }
      try {
        window.localStorage.setItem(TIMELINE_STORAGE_KEY, JSON.stringify(store));
      } catch (_retryErr) {
        // 仍失败：只保留当前条目，并截断 tool_result
        const fallback: TimelineStore = { [runId]: trimTimelineForStorage(timeline) };
        try {
          window.localStorage.setItem(TIMELINE_STORAGE_KEY, JSON.stringify(fallback));
        } catch (_finalErr) {
          // 最终兜底：清空后仅存当前条目（不保留 tool results）
          const minimal: TimelineStore = {
            [runId]: timeline.map(item => {
              if (item.kind === 'event') {
                const ev = { ...item.event, tool_result: null };
                return { kind: 'event' as const, event: ev };
              }
              return item;
            }),
          };
          try { window.localStorage.setItem(TIMELINE_STORAGE_KEY, JSON.stringify(minimal)); } catch { /* 静默失败 */ }
        }
      }
    }
    // 其他错误静默忽略 — localStorage 是缓存层，不应阻塞主流程
  }
}

export function hasOpenToolCalls(timeline: StreamingItem[]): boolean {
  const openCallIds = new Set<string>();

  timeline.forEach((item, index) => {
    if (item.kind !== 'event') return;
    const event = item.event;
    const key = event.tool_call_id || `${event.tool_name ?? 'tool'}:${event.index ?? index}`;

    if (event.type === 'assistant_tool_call') {
      openCallIds.add(key);
    } else if (event.type === 'tool_result' || event.type === 'tool_error') {
      openCallIds.delete(key);
    }
  });

  return openCallIds.size > 0;
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
    } else if (e.type === 'assistant_text' || e.type === 'final_answer') {
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
