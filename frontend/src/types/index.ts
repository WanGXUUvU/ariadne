export interface SessionSummary {
  session_id: string;
  session_name?: string;
  created_at: string;
  updated_at: string;
  last_agent_name?: string | null;
  last_skill_name?: string | null;
  message_count: number;
  last_reply_preview?: string | null;
}

export interface AgentMessage {
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string | null;
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
  type: 'assistant_tool_call' | 'tool_result' | 'tool_error' | 'final_answer';
  content?: string | null;
  tool_name?: string | null;
  tool_call_id?: string | null;
  tool_result?: ToolResult | null;
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
