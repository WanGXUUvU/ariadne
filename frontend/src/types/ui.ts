export type ViewMode = 'chat' | 'skills' | 'knowledge' | 'settings';

export interface UiAgentOption {
  id: string;
  name: string;
  description: string;
  icon: string;
  is_builtin?: boolean;
}
