<script setup lang="ts">
import type { ApprovalInfo } from '../types';

const props = defineProps<{
  approval: ApprovalInfo;
  isLoading: boolean;
}>();

const emit = defineEmits<{
  approve: [];
  reject: [];
  approveAll: [];
}>();

// 格式化 arguments：尝试 JSON 美化，失败则原样返回
function formatArgs(raw: string): string {
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}
</script>

<template>
  <div class="approval-card">
    <div class="approval-header">
      <span class="approval-icon">🔐</span>
      <span class="approval-title">工具调用需要审批</span>
    </div>

    <div class="approval-body">
      <div class="tool-row">
        <span class="tool-label">工具</span>
        <span class="tool-name">{{ approval.tool_name }}</span>
      </div>
      <div v-if="approval.arguments" class="args-row">
        <span class="tool-label">参数</span>
        <pre class="args-pre">{{ formatArgs(approval.arguments) }}</pre>
      </div>
      <div v-else class="args-row args-loading">
        <span class="tool-label">参数</span>
        <span class="args-placeholder">加载中...</span>
      </div>
    </div>

    <div class="approval-actions">
      <button
        class="action-btn btn-approve"
        :disabled="isLoading"
        @click="emit('approve')"
        title="批准此次调用"
      >
        <span class="btn-icon">✓</span>
        批准
      </button>
      <button
        class="action-btn btn-approve-all"
        :disabled="isLoading"
        @click="emit('approveAll')"
        title="切换到全自动模式，之后不再询问"
      >
        <span class="btn-icon">⚡</span>
        全部允许
      </button>
      <button
        class="action-btn btn-reject"
        :disabled="isLoading"
        @click="emit('reject')"
        title="拒绝此次工具调用"
      >
        <span class="btn-icon">✕</span>
        拒绝
      </button>
    </div>
  </div>
</template>

<style scoped>
.approval-card {
  margin: 8px 16px 4px;
  border: 1px solid var(--border-color, #e5a800);
  border-radius: 10px;
  background: var(--approval-bg, rgba(229, 168, 0, 0.06));
  overflow: hidden;
  font-size: 13px;
}

.approval-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px 8px;
  border-bottom: 1px solid var(--border-color, rgba(229, 168, 0, 0.2));
  background: rgba(229, 168, 0, 0.08);
}

.approval-icon {
  font-size: 15px;
}

.approval-title {
  font-weight: 600;
  color: var(--text-primary, #c8a800);
  letter-spacing: 0.3px;
}

.approval-body {
  padding: 10px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.tool-row,
.args-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.tool-label {
  flex-shrink: 0;
  width: 36px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-secondary, #888);
  padding-top: 2px;
}

.tool-name {
  font-family: var(--font-mono, monospace);
  font-size: 13px;
  color: var(--text-primary, #e0c060);
  background: rgba(255, 255, 255, 0.04);
  padding: 1px 6px;
  border-radius: 4px;
  border: 1px solid rgba(255,255,255,0.08);
}

.args-pre {
  margin: 0;
  padding: 6px 10px;
  background: rgba(0,0,0,0.2);
  border-radius: 6px;
  border: 1px solid rgba(255,255,255,0.07);
  font-family: var(--font-mono, monospace);
  font-size: 12px;
  color: var(--text-secondary, #aaa);
  max-height: 120px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
  flex: 1;
}

.args-placeholder {
  color: var(--text-dim, #666);
  font-style: italic;
}

.approval-actions {
  display: flex;
  gap: 8px;
  padding: 10px 14px;
  border-top: 1px solid rgba(255,255,255,0.06);
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 6px 14px;
  border-radius: 6px;
  border: 1px solid transparent;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  letter-spacing: 0.3px;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-icon {
  font-size: 12px;
}

.btn-approve {
  background: rgba(34, 197, 94, 0.15);
  border-color: rgba(34, 197, 94, 0.35);
  color: #4ade80;
}
.btn-approve:not(:disabled):hover {
  background: rgba(34, 197, 94, 0.25);
  border-color: rgba(34, 197, 94, 0.6);
}

.btn-approve-all {
  background: rgba(234, 179, 8, 0.12);
  border-color: rgba(234, 179, 8, 0.35);
  color: #fbbf24;
}
.btn-approve-all:not(:disabled):hover {
  background: rgba(234, 179, 8, 0.22);
  border-color: rgba(234, 179, 8, 0.6);
}

.btn-reject {
  background: rgba(239, 68, 68, 0.12);
  border-color: rgba(239, 68, 68, 0.3);
  color: #f87171;
  margin-left: auto;
}
.btn-reject:not(:disabled):hover {
  background: rgba(239, 68, 68, 0.22);
  border-color: rgba(239, 68, 68, 0.55);
}
</style>
