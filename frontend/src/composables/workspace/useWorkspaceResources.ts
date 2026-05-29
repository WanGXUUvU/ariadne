import { computed, ref, type Ref } from 'vue';

import { api } from '../../api/client';
import { settingsApi, type ModelSetting } from '../../api/settings';
import type { SkillMetadata } from '../../types';
import type { UiAgentOption } from '../../types/ui';

type ModelConfigPatch = {
  model_id?: string | null;
  model_provider_id?: number | null;
  thinking_enabled?: boolean;
  thinking_effort?: string;
};

type UseWorkspaceResourcesOptions = {
  activeSessionId: Ref<string | null>;
  errorMsg: Ref<string | null>;
};

export function useWorkspaceResources({
  activeSessionId,
  errorMsg,
}: UseWorkspaceResourcesOptions) {
  const skills = ref<SkillMetadata[]>([]);
  const isSkillsLoading = ref(false);

  const availableAgents = ref<UiAgentOption[]>([]);
  const activeAgentId = ref('default');

  const modelId = ref<string | null>(null);
  const modelProviderId = ref<number | null>(null);
  const thinkingEnabled = ref(false);
  const thinkingEffort = ref('medium');
  const enabledModels = ref<ModelSetting[]>([]);

  const activeAgent = computed(() =>
    availableAgents.value.find((agent) => agent.id === activeAgentId.value) ?? availableAgents.value[0] ?? null,
  );

  const activeModelContextLength = computed(() => {
    if (!modelId.value) return 128000;
    const currentModel = enabledModels.value.find((model) => model.model_id === modelId.value);
    return currentModel?.context_length ?? 128000;
  });

  const loadEnabledModels = async () => {
    try {
      enabledModels.value = await settingsApi.listEnabledModels();
    } catch {
      // ignore model catalog failures during bootstrap
    }
  };

  const loadSkills = async () => {
    try {
      isSkillsLoading.value = true;
      skills.value = await api.getSkills();
    } catch (err: any) {
      errorMsg.value = 'Failed to load skills: ' + err.message;
    } finally {
      isSkillsLoading.value = false;
    }
  };

  const toggleSkill = async (skillName: string, currentlyEnabled: boolean) => {
    try {
      if (currentlyEnabled) {
        await api.disableSkill(skillName);
      } else {
        await api.enableSkill(skillName);
      }
      await loadSkills();
    } catch (err: any) {
      errorMsg.value = 'Failed to toggle skill: ' + err.message;
    }
  };

  const fetchAgents = async () => {
    try {
      const data = await api.getAgents();
      availableAgents.value = (data ?? []).map((agent) => ({
        id: agent.id,
        name: agent.name,
        description: agent.description ?? '',
        icon: '\ud83e\udd16',
        is_builtin: agent.is_builtin,
      }));
      if (availableAgents.value.length > 0 && !availableAgents.value.find((agent) => agent.id === activeAgentId.value)) {
        activeAgentId.value = availableAgents.value[0].id;
      }
    } catch {
      // keep empty on failure
    }
  };

  const saveAgent = async (definition: {
    id: string;
    name: string;
    description: string;
    system_prompt: string;
    tool_names: string[] | null;
  }) => {
    await api.saveAgent(definition);
    await fetchAgents();
  };

  const deleteAgent = async (agentId: string) => {
    await api.deleteAgent(agentId);
    await fetchAgents();
    if (activeAgentId.value === agentId) {
      activeAgentId.value = 'default';
    }
  };

  const updateModelConfig = async (config: ModelConfigPatch) => {
    if (!activeSessionId.value) return;
    if (config.model_id !== undefined) modelId.value = config.model_id;
    if (config.model_provider_id !== undefined) modelProviderId.value = config.model_provider_id;
    if (config.thinking_enabled !== undefined) thinkingEnabled.value = config.thinking_enabled;
    if (config.thinking_effort !== undefined) thinkingEffort.value = config.thinking_effort;
    try {
      await api.patchSession(activeSessionId.value, config);
    } catch (err: any) {
      errorMsg.value = 'Failed to update model config: ' + err.message;
    }
  };

  return {
    skills,
    isSkillsLoading,
    availableAgents,
    activeAgentId,
    activeAgent,
    modelId,
    modelProviderId,
    thinkingEnabled,
    thinkingEffort,
    enabledModels,
    activeModelContextLength,
    loadEnabledModels,
    loadSkills,
    toggleSkill,
    fetchAgents,
    saveAgent,
    deleteAgent,
    updateModelConfig,
    settingsApi,
  };
}
