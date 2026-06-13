import type { RunEvent, ApprovalInfo, TraceRunSummary } from '../types';

const sameApproval = (left: ApprovalInfo, right: ApprovalInfo) => {
  if (left.approval_id && right.approval_id) return left.approval_id === right.approval_id;
  if (left.tool_call_id && right.tool_call_id) return left.tool_call_id === right.tool_call_id;
  return false;
};

export const upsertPendingApproval = (
  approvals: ApprovalInfo[],
  next: ApprovalInfo,
): ApprovalInfo[] => {
  const idx = approvals.findIndex(item => sameApproval(item, next));
  if (idx === -1) return [...approvals, next];

  const merged = {
    ...approvals[idx],
    ...next,
    arguments: next.arguments || approvals[idx].arguments,
    tool_name: next.tool_name || approvals[idx].tool_name,
    run_id: next.run_id || approvals[idx].run_id,
    tool_call_id: next.tool_call_id || approvals[idx].tool_call_id,
  };
  return approvals.map((item, itemIdx) => itemIdx === idx ? merged : item);
};

export const removePendingApproval = (
  approvals: ApprovalInfo[],
  approvalId: string,
): ApprovalInfo[] => approvals.filter(item => item.approval_id !== approvalId);

export const findPendingApprovalForTool = (
  approvals: ApprovalInfo[],
  toolCallId?: string | null,
  toolName?: string | null,
  approvalId?: string | null,
): ApprovalInfo | null => {
  if (approvalId) {
    const byApprovalId = approvals.find(item => item.approval_id === approvalId);
    if (byApprovalId) return byApprovalId;
  }

  if (toolCallId) {
    const byToolCallId = approvals.find(item => item.tool_call_id === toolCallId);
    if (byToolCallId) return byToolCallId;
  }

  const unresolvedWithoutCallId = approvals.filter(item => !item.tool_call_id);
  if (!toolCallId && toolName && unresolvedWithoutCallId.length === 1) {
    const only = unresolvedWithoutCallId[0];
    if (only.tool_name === toolName) return only;
  }

  return null;
};

export const extractPendingApprovalsFromTraceRuns = (
  runs: TraceRunSummary[],
): ApprovalInfo[] => {
  const output: ApprovalInfo[] = [];

  for (const run of runs) {
    const callEvents = run.events.filter(e => e.type === 'assistant_tool_call');
    const resultEvents = run.events.filter(e => e.type === 'tool_result' || e.type === 'tool_error');
    const approvalEvents = run.events.filter(e => e.type === 'approval_required');

    for (const approvalEvent of approvalEvents) {
      const approvalId = approvalEvent.content;
      if (!approvalId) continue;

      const toolCallId = approvalEvent.tool_call_id ?? undefined;
      const hasResult = toolCallId
        ? resultEvents.some(result => result.tool_call_id === toolCallId)
        : false;
      if (hasResult) continue;

      const callEvent = findMatchingCallEvent(callEvents, approvalEvent);
      const next: ApprovalInfo = {
        approval_id: approvalId,
        tool_name: approvalEvent.tool_name || callEvent?.tool_name || '',
        arguments: callEvent?.content || '',
        run_id: run.run_id,
        tool_call_id: toolCallId,
      };

      if (!output.some(item => sameApproval(item, next))) {
        output.push(next);
      }
    }
  }

  return output;
};

const findMatchingCallEvent = (
  callEvents: RunEvent[],
  approvalEvent: RunEvent,
): RunEvent | undefined => {
  if (approvalEvent.tool_call_id) {
    return callEvents.find(call => call.tool_call_id === approvalEvent.tool_call_id);
  }
  return callEvents.find(call => call.tool_name === approvalEvent.tool_name);
};
