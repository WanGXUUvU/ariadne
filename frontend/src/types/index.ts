export interface ChildAgentInfo {
  run_id: string;
  agent_name: string;
  status: 'running' | 'done' | 'error' | 'not_found';
  reply: string | null;
  error: string | null;
}

export interface SessionSummary {
  session_id: string;
  session_name?: string;
  created_at: string;
  updated_at: string;
  last_agent_name?: string | null;
  last_skill_name?: string | null;
  message_count: number;
  last_reply_preview?: string | null;
  permission_profile?: string | null;
  context_tokens?: number | null;
}

export interface AgentMessage {
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string | null;
  timeline?: StreamingItem[];   // 客户端专属：本轮 streaming 时间线，持久保留
  stopped?: boolean;            // 客户端专属：用户主动 Stop，内容为截断版本
}

export interface SessionState {
  messages: AgentMessage[];
}

export interface SessionDetail extends SessionSummary {
  state: SessionState;
}

export interface ApiError {
  code?: string;
  message: string;
}

export interface RunResponse {
  reply: string;
  state: SessionState;
  events: AgentEvent[];
  metadata: any;
  error?: ApiError;
}

export interface ToolError {
  code: string;
  tool_name: string;
  message: string;
}

export interface ToolResult {
  ok: boolean;
  content?: string | null;
  error?: ToolError | null;
  metadata?: Record<string, any>;
}

export interface AgentEvent {
  index: number;
  type: 'assistant_tool_call' | 'tool_result' | 'tool_error' | 'final_answer' | 'approval_required' | 'approval_rejected';
  content?: string | null;
  tool_name?: string | null;
  tool_call_id?: string | null;
  tool_result?: ToolResult | null;
}

export interface ApprovalInfo {
  approval_id: string;
  tool_name: string;
  arguments: string;
  run_id: string;
}

export interface TraceRunSummary {
  run_id: string;
  session_id: string;
  agent_name?: string | null;
  skill_name?: string | null;
  user_input: string;
  reply: string;
  event_count: number;
  created_at: string;
  finished_at: string;
  events: AgentEvent[];
}

export interface TraceResponse {
  session_id: string;
  runs: TraceRunSummary[];
}

export interface SkillMetadata {
  name: string;
  description: string;
  path: string;
  enabled: boolean;
  error?: string | null;
}

export interface CompactResponse {
  state: SessionState;
  did_compact: boolean;
  removed_count: number;
}

// SSE streaming frame types
export interface StreamStartData {
  session_id: string;
  run_id: string;
  agent_name: string;
  skill_name: string | null;
}

export interface StreamDeltaData {
  content: string;
}

export interface StreamThinkingDeltaData {
  content: string;
}

export interface StreamEndData {
  reply: string;
  state: SessionState;
  metadata: { session_id: string; run_id: string; agent_name: string; skill_name: string | null };
}

export interface StreamErrorData {
  message: string;
}

export interface StreamPausedData {
  run_id: string;
  approval_id?: string;
}

export type StreamFrame =
  | { type: 'start';          data: StreamStartData }
  | { type: 'agent_event';    data: AgentEvent }
  | { type: 'delta';          data: StreamDeltaData }
  | { type: 'thinking_delta'; data: StreamThinkingDeltaData }
  | { type: 'end';            data: StreamEndData }
  | { type: 'error';          data: StreamErrorData }
  | { type: 'paused';         data: StreamPausedData }
  | { type: 'resume';         data: StreamStartData };

// 统一时间线：文字和工具事件按到达顺序混排
export type StreamingItem =
  | { kind: 'text';     content: string }
  | { kind: 'thinking'; content: string }
  | { kind: 'event';    event: AgentEvent };
