<script setup lang="ts">
import type { AgentMessage } from '../types';
import type { UiAgentOption } from '../types/ui';
import MessageList from './MessageList.vue';
import MessageComposer from './MessageComposer.vue';

defineProps<{
  messages: AgentMessage[];
  isLoading: boolean;
  isCompacting: boolean;
  error: string | null;
  infoMsg: string | null; // 成功/信息提示，绿色显示
  hasSession: boolean;
  sessionTitle: string;
  agents: UiAgentOption[];
  activeAgentId: string;
}>();

const emit = defineEmits<{
  (e: 'send', text: string): void;
  (e: 'errorDismiss'): void;
  (e: 'infoDismiss'): void; // 手动关闭 info 提示
  (e: 'update:activeAgentId', id: string): void;
  (e: 'compact'): void;
  (e: 'reset'): void;
}>();

const handleReset = () => {
  if (confirm('Reset this session? This will clear all chat history.')) {
    emit('reset');
  }
};
</script>

<template>
  <main v-if="!hasSession" class="chat-panel" style="align-items: center; justify-content: center; background: var(--bg-app);">
    <div style="text-align: center; max-width: 400px; padding: 40px; border: 1px dashed var(--border-strong); border-radius: var(--radius-sm);">
      <svg viewBox="0 0 24 24" width="24" height="24" stroke="var(--text-secondary)" stroke-width="1.5" fill="none" style="margin-bottom: 16px;"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="3" y1="9" x2="21" y2="9"></line></svg>
      <div class="mono-label" style="margin-bottom: 8px;">NO ACTIVE WORKSPACE</div>
      <p style="color: var(--text-secondary); font-size: 13px;">Select a session from the sidebar or create a new one to begin execution.</p>
    </div>
  </main>

  <main v-else class="chat-panel">
    <header class="panel-header">
      <div style="display: flex; align-items: center; gap: 16px;">
        <span class="mono-label">{{ sessionTitle }}</span>
        <div style="display: flex; align-items: center; gap: 6px;">
          <span style="width: 6px; height: 6px; border-radius: 50%;" :style="{ background: isLoading ? '#F5A623' : '#50E3C2' }"></span>
          <span class="mono-label" style="font-size: 10px;">{{ isLoading ? 'EXECUTING' : 'IDLE' }}</span>
        </div>
      </div>
      
      <div style="display: flex; gap: 8px; align-items: center;">
        <select 
          :value="activeAgentId" 
          @change="$emit('update:activeAgentId', ($event.target as HTMLSelectElement).value)"
          class="tech-btn"
          style="appearance: none; padding-right: 24px; background-image: url('data:image/svg+xml;charset=US-ASCII,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2224%22%20height%3D%2224%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%23EDEDED%22%20stroke-width%3D%222%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpolyline%20points%3D%226%209%2012%2015%2018%209%22%3E%3C%2Fpolyline%3E%3C%2Fsvg%3E'); background-repeat: no-repeat; background-position: right 6px center; background-size: 12px;"
        >
          <option v-for="agent in agents" :key="agent.id" :value="agent.id">
            {{ agent.name }}
          </option>
        </select>
        
        <button 
          class="tech-btn" 
          @click="$emit('compact')"
          :disabled="isCompacting || isLoading"
        >
          <!-- isCompacting 时显示闪烁动画，正常时显示图标+文字 -->
          <template v-if="isCompacting">
            <span class="blink" style="color: var(--text-muted); margin-right: 4px;">●</span>
            COMPACTING...
          </template>
          <template v-else>
            <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none"><path d="M4 14h6v6"></path><path d="M20 10h-6V4"></path><path d="M14 10l7-7"></path><path d="M3 21l7-7"></path></svg>
            Compact
          </template>
        </button>
        
        <button 
          class="tech-btn" 
          @click="handleReset" 
          style="color: var(--danger, #FF453A); border-color: rgba(255,69,58,0.3);"
        >
          Reset
        </button>
      </div>
    </header>
    
    <!-- 红色错误条 -->
    <div v-if="error" style="background: rgba(255,69,58,0.1); border-bottom: 1px solid rgba(255,69,58,0.2); color: #FF453A; padding: 12px 20px; font-size: 13px; display: flex; justify-content: space-between; font-family: var(--font-mono);">
      <span>ERR: {{ error }}</span>
      <button style="background: transparent; border: none; color: inherit; cursor: pointer;" @click="$emit('errorDismiss')">✕</button>
    </div>

    <!-- 绿色信息条（compact 成功、已最新等）-->
    <div v-if="infoMsg" style="background: rgba(80,227,194,0.08); border-bottom: 1px solid rgba(80,227,194,0.2); color: #50E3C2; padding: 12px 20px; font-size: 13px; display: flex; justify-content: space-between; font-family: var(--font-mono);">
      <span>{{ infoMsg }}</span>
      <button style="background: transparent; border: none; color: inherit; cursor: pointer;" @click="$emit('infoDismiss')">✕</button>
    </div>

    <MessageList 
      :messages="messages" 
      :isLoading="isLoading" 
      :isCompacting="isCompacting"
    />
    
    <MessageComposer 
      :disabled="isLoading || isCompacting"
      :messageCount="messages.length"
      @send="$emit('send', $event)" 
    />
  </main>
</template>

<style scoped>
/* No specific styles needed */
</style>
