/**
 * settings.ts
 * 职责：封装所有 /settings/* 接口，供 SettingsPanel 和 ModelSelector 使用。
 * 不负责：业务状态管理（那是 composable 的事）
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

async function fetchSettings<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
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
    throw new Error(data?.detail || data?.error?.message || 'Settings API Error');
  }
  return data as T;
}

// ─────────────────────────────────────────────
//  类型定义
// ─────────────────────────────────────────────

export interface Provider {
  id: number;
  name: string;
  base_url: string;
  api_key_hint: string; // 脱敏，如 "****abcd"
  is_default: boolean; // 是否为默认服务商
}

export interface ModelSetting {
  id: number;
  provider_id: number;
  model_id: string;
  display_name: string;
  enabled: boolean;
  supports_thinking: boolean;
  thinking_style: string;
  effort_levels: string[]; // ["low","high"] 等
  context_length: number | null;
  supports_tools: boolean;
}

// ─────────────────────────────────────────────
//  API 集合
// ─────────────────────────────────────────────

export const settingsApi = {
  /** 列出所有 Provider（api_key 已脱敏） */
  listProviders(): Promise<Provider[]> {
    return fetchSettings<Provider[]>('/settings/providers');
  },

  /** 创建新 Provider */
  createProvider(data: { name: string; base_url: string; api_key: string }): Promise<Provider> {
    return fetchSettings<Provider>('/settings/providers', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  /** 删除 Provider（级联删除其 model_settings） */
  deleteProvider(id: number): Promise<void> {
    return fetchSettings<void>(`/settings/providers/${id}`, { method: 'DELETE' });
  },

  /**
   * 同步该 Provider 的模型列表
   * 后端会调用 {base_url}/v1/models，解析并写入 model_settings
   */
  syncModels(providerId: number): Promise<ModelSetting[]> {
    return fetchSettings<ModelSetting[]>(`/settings/providers/${providerId}/models`);
  },

  /** 更新模型设置（enabled / display_name） */
  patchModel(id: number, patch: { enabled?: boolean; display_name?: string }): Promise<ModelSetting> {
    return fetchSettings<ModelSetting>(`/settings/models/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    });
  },

  /** 编辑 Provider 信息（name / base_url / api_key 均可选） */
  patchProvider(id: number, patch: { name?: string; base_url?: string; api_key?: string }): Promise<Provider> {
    return fetchSettings<Provider>(`/settings/providers/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    });
  },

  /** 将某个 Provider 设为默认服务商 */
  setDefaultProvider(id: number): Promise<Provider> {
    return fetchSettings<Provider>(`/settings/providers/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ is_default: true }),
    });
  },

  /** 获取所有 enabled=true 的模型，供对话框 ModelSelector 使用 */
  listEnabledModels(): Promise<ModelSetting[]> {
    return fetchSettings<ModelSetting[]>('/settings/models?enabled=true');
  },

  /** 获取 settings.json 物理文件内容 */
  getSettingsFile(): Promise<any> {
    return fetchSettings<any>('/settings/file');
  },

  /** 更新 settings.json 物理文件内容 */
  updateSettingsFile(data: any): Promise<any> {
    return fetchSettings<any>('/settings/file', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },
};
