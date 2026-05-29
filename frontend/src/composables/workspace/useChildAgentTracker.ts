import { ref } from 'vue';

import { api } from '../../api/client';
import type { AgentEvent, AgentMessage, ChildAgentInfo, TraceRunSummary } from '../../types';

export function useChildAgentTracker() {
  const childAgentsBySession = ref<Record<string, ChildAgentInfo[]>>({});
  let childPollTimer: ReturnType<typeof setInterval> | null = null;

  function startChildPolling() {
    if (childPollTimer !== null) return;
    childPollTimer = setInterval(async () => {
      let anyRunning = false;
      for (const [sessionId, children] of Object.entries(childAgentsBySession.value)) {
        for (const child of children) {
          if (child.status === 'running') {
            anyRunning = true;
            try {
              const res = await api.getChildRunStatus(child.run_id);
              child.status = res.status as ChildAgentInfo['status'];
              child.reply = res.reply;
              child.error = res.error;
            } catch {
              // ignore transient polling failures
            }
          }
        }
        childAgentsBySession.value[sessionId] = [...children];
      }
      if (!anyRunning) {
        clearInterval(childPollTimer!);
        childPollTimer = null;
      }
    }, 2000);
  }

  function onLiveAgentEvent(sessionId: string, ev: AgentEvent) {
    if (ev.type !== 'tool_result' || ev.tool_name !== 'spawn_child_agent' || !ev.tool_result?.ok) return;
    const runId = ev.tool_result.content ?? '';
    const agentName = (ev.tool_result.metadata?.agent_name as string) ?? '子Agent';
    if (!runId) return;
    const existing = childAgentsBySession.value[sessionId] ?? [];
    if (existing.find(c => c.run_id === runId)) return;
    childAgentsBySession.value[sessionId] = [
      ...existing,
      { run_id: runId, agent_name: agentName, status: 'running', reply: null, error: null },
    ];
    startChildPolling();
  }

  function extractChildAgents(sessionId: string, msgs: AgentMessage[], traceRuns: TraceRunSummary[]) {
    const children: ChildAgentInfo[] = [];
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

    if (children.length === 0) {
      for (const run of traceRuns) {
        for (const event of run.events) {
          if (event.type === 'tool_result' && event.tool_name === 'spawn_child_agent' && event.tool_result?.ok) {
            const runId = event.tool_result.content ?? '';
            const agentName = (event.tool_result.metadata?.agent_name as string) ?? '子Agent';
            if (runId && !children.find(c => c.run_id === runId)) {
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

  function clearChildAgents(sessionId: string) {
    delete childAgentsBySession.value[sessionId];
  }

  return {
    childAgentsBySession,
    onLiveAgentEvent,
    extractChildAgents,
    clearChildAgents,
  };
}
