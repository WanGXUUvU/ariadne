import type { UiAgentOption } from '../types/ui';

export const MOCK_AGENTS: UiAgentOption[] = [
  {
    id: 'default',
    name: 'Default Agent',
    description: 'The standard assistant with general capabilities.',
    icon: '🤖'
  },
  {
    id: 'code_agent',
    name: 'Code Expert',
    description: 'Specialized in writing and debugging code.',
    icon: '💻'
  },
  {
    id: 'data_agent',
    name: 'Data Analyst',
    description: 'Expert at parsing and visualizing datasets.',
    icon: '📊'
  }
];

export const MOCK_EVENT_ICONS: Record<string, string> = {
  'tool_call': '🔧',
  'tool_result': '✅',
  'tool_error': '❌',
  'agent_start': '🚀',
  'agent_finish': '🏁',
  'compact_history': '🗜️'
};
