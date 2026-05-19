<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue';
import { api } from '../api/client';
import type { UiAgentOption } from '../types/ui';

interface AgentDefinition {
  id: string;
  name: string;
  description: string;
  system_prompt: string;
  tool_names: string[] | null;
}

const props = defineProps<{
  isOpen: boolean;
  agents: UiAgentOption[];
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'save', definition: AgentDefinition): void;
  (e: 'delete', agent_id: string): void;
}>();

// 当前选中的 agent id
const selectedId = ref<string | null>(null);

// 是否是新建模式（id 字段可编辑）
const isNew = ref(false);

// 表单状态
const form = ref<AgentDefinition>({
  id: '',
  name: '',
  description: '',
  system_prompt: '',
  tool_names: null,
});

// tool_names 用逗号分隔的字符串来编辑
const toolNamesInput = ref('');

function syncSelectedToolsFromInput() {
  const trimmed = toolNamesInput.value.trim();
  selectedTools.value = trimmed ? trimmed.split(',').map(s => s.trim()).filter(Boolean) : [];
}

// 操作反馈
const feedback = ref<{ type: 'success' | 'error'; msg: string } | null>(null);
const isSaving = ref(false);
const isDeleting = ref(false);

// 可用工具列表（从后端获取）
const availableTools = ref<string[]>([]);
const selectedTools = ref<string[]>([]);

onMounted(async () => {
  try {
    const data = await api.getTools();
    availableTools.value = (data ?? []).map((t: { name: string }) => t.name);
  } catch {
    // 加载失败不影响表单其他功能
  }
});

// 面板打开时默认选中第一个
watch(() => props.isOpen, (open) => {
  if (open && props.agents.length > 0 && !selectedId.value) {
    selectAgentById(props.agents[0].id);
  }
  feedback.value = null;
});

// agents 列表加载后，若还没选中则选第一个
watch(() => props.agents, (list) => {
  if (list.length > 0 && !selectedId.value) {
    selectAgentById(list[0].id);
  }
}, { immediate: true });

function selectAgentById(id: string) {
  const agent = props.agents.find(a => a.id === id);
  if (!agent) return;
  selectedId.value = id;
  isNew.value = false;
  form.value = {
    id: agent.id,
    name: agent.name,
    description: agent.description ?? '',
    system_prompt: '',   // 列表接口不含 system_prompt，留空让用户填
    tool_names: null,
  };
  selectedTools.value = [];
  feedback.value = null;
}

function createNew() {
  selectedId.value = null;
  isNew.value = true;
  form.value = { id: '', name: '', description: '', system_prompt: '', tool_names: null };
  selectedTools.value = [];
  feedback.value = null;
}

const toolNamesArray = computed<string[] | null>(() =>
  selectedTools.value.length > 0 ? [...selectedTools.value] : null
);

async function save() {
  if (!form.value.id.trim()) { feedback.value = { type: 'error', msg: 'ID 不能为空' }; return; }
  if (!form.value.name.trim()) { feedback.value = { type: 'error', msg: '名称不能为空' }; return; }
  if (!form.value.system_prompt.trim()) { feedback.value = { type: 'error', msg: 'System Prompt 不能为空' }; return; }

  isSaving.value = true;
  feedback.value = null;
  try {
    const definition: AgentDefinition = {
      ...form.value,
      id: form.value.id.trim(),
      tool_names: toolNamesArray.value,
    };
    emit('save', definition);
    selectedId.value = definition.id;
    isNew.value = false;
    feedback.value = { type: 'success', msg: '保存成功' };
  } finally {
    isSaving.value = false;
  }
}

async function deleteAgent() {
  if (!selectedId.value) return;
  if (!confirm(`确认删除 "${form.value.name}"？Builtin agent 无法真正删除。`)) return;
  isDeleting.value = true;
  feedback.value = null;
  try {
    emit('delete', selectedId.value);
    selectedId.value = null;
    feedback.value = { type: 'success', msg: '已发送删除请求，列表将刷新' };
  } finally {
    isDeleting.value = false;
  }
}
</script>

<template>
  <div v-if="isOpen" class="agent-modal-overlay" @click.self="$emit('close')">
    <div class="agent-manager">

      <!-- Header -->
      <header class="am-header">
        <div class="am-header-top">
          <div class="am-title-row">
            <span class="mono-label">AGENTS</span>
          </div>
          <div class="am-actions">
            <button class="tech-btn" @click="createNew">
              <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
              New Agent
            </button>
            <button class="tech-btn icon-btn" @click="$emit('close')">
              <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
          </div>
        </div>
      </header>

      <!-- Body: list + form -->
      <div class="am-body">

        <!-- Left: agent list -->
        <div class="am-list">
          <div
            v-for="agent in agents"
            :key="agent.id"
            class="am-item"
            :class="{ active: selectedId === agent.id }"
            @click="selectAgentById(agent.id)"
          >
            <span class="am-item-icon">🤖</span>
            <div class="am-item-info">
              <div class="am-item-name">{{ agent.name }}</div>
              <div class="am-item-id mono-label">{{ agent.id }}</div>
            </div>
          </div>
          <div v-if="agents.length === 0" class="am-empty">No agents yet.</div>
        </div>

        <!-- Right: edit form -->
        <div class="am-form-panel">
          <div v-if="!selectedId && !isNew" class="am-placeholder">
            <span class="mono-label">SELECT AN AGENT OR CREATE A NEW ONE</span>
          </div>

          <form v-else class="am-form" @submit.prevent="save">
            <div class="form-section">
              <label class="form-label mono-label">AGENT ID</label>
              <input
                v-model="form.id"
                class="form-input"
                :disabled="!isNew"
                placeholder="e.g. my_agent"
                spellcheck="false"
              />
              <span v-if="!isNew" class="form-hint">ID 创建后不可修改</span>
            </div>

            <div class="form-section">
              <label class="form-label mono-label">NAME</label>
              <input v-model="form.name" class="form-input" placeholder="Display name" />
            </div>

            <div class="form-section">
              <label class="form-label mono-label">DESCRIPTION</label>
              <input v-model="form.description" class="form-input" placeholder="One-line description" />
            </div>

            <div class="form-section grow">
              <label class="form-label mono-label">SYSTEM PROMPT</label>
              <textarea
                v-model="form.system_prompt"
                class="form-textarea"
                placeholder="你是一个...（留空表示沿用已有 system prompt）"
                spellcheck="false"
              />
            </div>

            <div class="form-section">
              <label class="form-label mono-label">TOOLS <span class="form-hint">不勾选表示不限制（使用全部工具）</span></label>
              <div class="tool-checkbox-list">
                <label
                  v-for="tool in availableTools"
                  :key="tool"
                  class="tool-checkbox-item"
                >
                  <input
                    type="checkbox"
                    :value="tool"
                    v-model="selectedTools"
                    class="tool-checkbox"
                  />
                  <span class="tool-name">{{ tool }}</span>
                </label>
                <div v-if="availableTools.length === 0" class="form-hint" style="padding: 6px 0;">
                  Loading tools...
                </div>
              </div>
            </div>

            <!-- Feedback -->
            <div v-if="feedback" class="form-feedback" :class="feedback.type">
              {{ feedback.msg }}
            </div>

            <!-- Actions -->
            <div class="form-actions">
              <button
                v-if="!isNew && selectedId"
                type="button"
                class="tech-btn danger-btn"
                :disabled="isDeleting"
                @click="deleteAgent"
              >
                <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6l-1 14H6L5 6"></path><path d="M10 11v6"></path><path d="M14 11v6"></path><path d="M9 6V4h6v2"></path></svg>
                {{ isDeleting ? 'Deleting...' : 'Delete' }}
              </button>
              <div style="flex: 1" />
              <button type="submit" class="tech-btn primary-btn" :disabled="isSaving">
                {{ isSaving ? 'Saving...' : 'Save Agent' }}
              </button>
            </div>
          </form>
        </div>
      </div>

    </div>
  </div>
</template>

<style scoped>
.agent-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(8px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.agent-manager {
  width: 100%;
  max-width: 960px;
  height: 100%;
  max-height: 80vh;
  background: var(--bg-app);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-app);
  color: var(--text-primary);
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.5);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Header */
.am-header {
  padding: 20px 28px 16px;
  border-bottom: 1px solid var(--border-dim);
  flex-shrink: 0;
}

.am-header-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.am-title-row {
  font-size: 13px;
  letter-spacing: 0.08em;
  color: var(--text-secondary);
}

.am-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

/* Body */
.am-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* Agent list */
.am-list {
  width: 240px;
  flex-shrink: 0;
  border-right: 1px solid var(--border-dim);
  overflow-y: auto;
  padding: 12px 0;
}

.am-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  cursor: pointer;
  transition: background var(--transition-fast);
  border-left: 2px solid transparent;
}

.am-item:hover {
  background: var(--bg-hover);
}

.am-item.active {
  background: var(--bg-hover);
  border-left-color: var(--accent);
}

.am-item-icon {
  font-size: 20px;
  line-height: 1;
  flex-shrink: 0;
}

.am-item-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.am-item-id {
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.am-empty {
  padding: 20px 16px;
  font-size: 13px;
  color: var(--text-secondary);
}

/* Form panel */
.am-form-panel {
  flex: 1;
  overflow-y: auto;
  padding: 24px 32px;
  display: flex;
  flex-direction: column;
}

.am-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  font-size: 12px;
  letter-spacing: 0.08em;
}

.am-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
  height: 100%;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-section.grow {
  flex: 1;
  min-height: 140px;
}

.form-label {
  font-size: 11px;
  letter-spacing: 0.08em;
  color: var(--text-secondary);
}

.form-hint {
  font-size: 11px;
  color: var(--text-secondary);
  font-weight: 400;
  letter-spacing: 0;
  margin-left: 8px;
}

.form-input {
  background: var(--bg-input, var(--bg-hover));
  border: 1px solid var(--border-dim);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 13px;
  padding: 8px 12px;
  outline: none;
  transition: border-color var(--transition-fast);
  font-family: var(--font-mono);
}

.form-input:focus {
  border-color: var(--border-strong);
}

.form-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.form-textarea {
  flex: 1;
  resize: none;
  background: var(--bg-input, var(--bg-hover));
  border: 1px solid var(--border-dim);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: 13px;
  padding: 10px 12px;
  outline: none;
  line-height: 1.6;
  font-family: var(--font-mono);
  transition: border-color var(--transition-fast);
  min-height: 120px;
}

.form-textarea:focus {
  border-color: var(--border-strong);
}

.form-feedback {
  font-size: 12px;
  padding: 8px 12px;
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
}

.form-feedback.success {
  background: rgba(52, 199, 89, 0.1);
  border: 1px solid rgba(52, 199, 89, 0.25);
  color: #34C759;
}

.form-feedback.error {
  background: rgba(255, 69, 58, 0.1);
  border: 1px solid rgba(255, 69, 58, 0.2);
  color: #FF453A;
}

.form-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 4px;
}

/* Buttons */
.tech-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 12px;
  font-family: var(--font-mono);
  background: transparent;
  border: 1px solid var(--border-dim);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  cursor: pointer;
  transition: var(--transition-fast);
  white-space: nowrap;
}

.tech-btn:hover {
  border-color: var(--border-strong);
  color: var(--text-primary);
}

.tech-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.tech-btn.icon-btn {
  padding: 6px;
}

.tech-btn.primary-btn {
  border-color: var(--accent);
  color: var(--accent);
}

.tech-btn.primary-btn:hover {
  background: var(--accent);
  color: #fff;
}

.tech-btn.danger-btn {
  border-color: rgba(255, 69, 58, 0.4);
  color: #FF453A;
}

.tech-btn.danger-btn:hover {
  background: rgba(255, 69, 58, 0.12);
  border-color: #FF453A;
}

.mono-label {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.06em;
}

/* Tools checkbox list */
.tool-checkbox-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 12px;
  background: var(--bg-input, var(--bg-hover));
  border: 1px solid var(--border-dim);
  border-radius: var(--radius-sm);
  min-height: 44px;
}

.tool-checkbox-item {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  padding: 3px 8px;
  border-radius: 4px;
  transition: background var(--transition-fast);
}

.tool-checkbox-item:hover {
  background: var(--bg-hover);
}

.tool-checkbox {
  accent-color: var(--accent);
  width: 13px;
  height: 13px;
  cursor: pointer;
}

.tool-name {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-secondary);
  user-select: none;
}

.tool-checkbox-item:has(.tool-checkbox:checked) .tool-name {
  color: var(--text-primary);
}
</style>
