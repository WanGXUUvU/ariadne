<script setup lang="ts">
import { computed, ref, watch, onBeforeUnmount } from 'vue';
import type { ApprovalInfo } from '../../types';

interface GroupedToolExecution {
  id: string;
  tool_name: string;
  status: 'running' | 'success' | 'error' | 'awaiting_approval';
  args: any;
  result?: any;
  error?: string;
  duration: string;
  groupCount?: number;
}

const props = defineProps<{
  exec: GroupedToolExecution;
  isAwaitingApproval?: boolean;
  pendingApprovalInfo?: ApprovalInfo | null;
  isProcessingApproval?: boolean;
}>();

const emit = defineEmits<{
  (e: 'approve'): void;
  (e: 'reject'): void;
  (e: 'approve-all'): void;
}>();

const isExpanded = ref(false);

const toggleExpand = () => {
  isExpanded.value = !isExpanded.value;
};

const formatJson = (val: any): string => {
  if (typeof val === 'string') {
    try {
      return JSON.stringify(JSON.parse(val), null, 2);
    } catch {
      return val;
    }
  }
  if (val && typeof val === 'object') {
    return JSON.stringify(val, null, 2);
  }
  return String(val);
};

const highlightJson = (json: string): string => {
  if (!json) return '';
  // Highlight keys, values, numbers, booleans
  return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g, (match) => {
    let cls = 'json-number';
    if (/^"/.test(match)) {
      if (/:$/.test(match)) {
        cls = 'json-key';
      } else {
        cls = 'json-string';
      }
    } else if (/true|false/.test(match)) {
      cls = 'json-boolean';
    } else if (/null/.test(match)) {
      cls = 'json-null';
    }
    return `<span class="${cls}">${match}</span>`;
  });
};

// Check if this specific tool card is currently waiting for approval
const isThisWaitingApproval = computed(() => {
  if (props.exec.status === 'awaiting_approval') return true;
  if (props.isAwaitingApproval && props.pendingApprovalInfo) {
    const pInfo = props.pendingApprovalInfo;
    const cid = pInfo.tool_call_id;
    if (cid && cid === props.exec.id) return true;
    if (!cid && pInfo.tool_name === props.exec.tool_name) return true;
  }
  return false;
});

// Code block copy handling
const copyState = ref<Record<string, boolean>>({});
const handleCopy = (key: string, text: string) => {
  navigator.clipboard.writeText(text).then(() => {
    copyState.value = { ...copyState.value, [key]: true };
    setTimeout(() => {
      copyState.value = { ...copyState.value, [key]: false };
    }, 2000);
  }).catch(err => {
    console.error('Copy failed:', err);
  });
};

const toolCnNameMap: Record<string, string> = {
  write_file: '写入文件 (write_file)',
  replace_file_content: '修改文件 (replace_file_content)',
  multi_replace_file_content: '批量修改文件 (multi_replace_file_content)',
  view_file: '读取文件 (view_file)',
  list_dir: '遍历目录 (list_dir)',
  grep_search: '搜索关键字 (grep_search)',
  web_search: '网页搜索 (web_search)',
  run_command: '运行指令 (run_command)',
  invoke_subagent: '启动子代理 (invoke_subagent)',
  define_subagent: '定义子代理 (define_subagent)',
};

const statusText = computed(() => {
  const toolName = props.exec.tool_name;
  const displayName = toolCnNameMap[toolName] || toolName;
  const status = props.exec.status;
  
  if (isThisWaitingApproval.value) {
    return `等待授权执行 ${displayName}...`;
  }
  
  if (status === 'running') {
    return `正在执行 ${displayName}...`;
  }
  
  if (status === 'success') {
    return `已成功执行 ${displayName}`;
  }
  
  if (status === 'error') {
    return `执行 ${displayName} 失败`;
  }
  
  return `已执行 ${displayName}`;
});</script>

<template>
  <!-- 连续重复调用：紧凑摘要行 -->
  <div
    v-if="exec.groupCount && exec.groupCount > 1"
    class="tool-exec-card tool-exec-group-summary"
  >
    <div class="tool-exec-header">
      <span class="tool-exec-name cute-status-text">
        连续执行了 {{ exec.groupCount }} 次 {{ exec.tool_name }} 操作
      </span>
    </div>
  </div>

  <!-- 单次工具调用或待审批工具调用 -->
  <div
    v-else
    class="tool-exec-card stagger-anim"
    :class="{ 
      'is-expanded': isExpanded || isThisWaitingApproval, 
      'has-error': exec.status === 'error',
      'is-awaiting-approval': isThisWaitingApproval 
    }"
  >
    <!-- 工具头部 -->
    <div class="tool-exec-header" @click="toggleExpand">
      <!-- 简单的文字执行状态描述（代替风趣动物） -->
      <span class="tool-exec-name cute-status-text" :class="`status-${exec.status}`">
        {{ statusText }}
      </span>
      
      <!-- 运行中状态指示器 (glowing dot) -->
      <span v-if="exec.status === 'running'" class="running-indicator">
        <span class="pulse-dot"></span>
      </span>

      <!-- 审批挂起微章 -->
      <span v-else-if="isThisWaitingApproval" class="approval-pulse-badge">
        <span class="pulse-dot-amber"></span>
        PENDING APPROVAL
      </span>

      <div class="tool-exec-meta" @click.stop>
        <span v-if="exec.status === 'error'" class="status-error-label">failed</span>
        <span v-else-if="!isThisWaitingApproval" class="duration-label">{{ exec.duration }}</span>
        
        <button class="header-chevron-btn" @click="toggleExpand">
          <svg class="toggle-chevron" :class="{ open: isExpanded || isThisWaitingApproval }" viewBox="0 0 24 24" width="11" height="11" stroke="currentColor" stroke-width="2.5" fill="none">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- 工具折叠体内容 -->
    <div class="tool-exec-body" v-if="isExpanded || isThisWaitingApproval">
      <!-- 参数 -->
      <div class="tool-exec-section" v-if="exec.args && Object.keys(exec.args).length > 0">
        <div class="ide-code-container">
          <div class="ide-code-header">
            <div class="mac-control-dots">
              <span class="dot close"></span>
              <span class="dot minimize"></span>
              <span class="dot expand"></span>
            </div>
            <span class="ide-tab-title">parameters.json</span>
            <button class="ide-copy-btn" :class="{ copied: copyState['args'] }" @click="handleCopy('args', formatJson(exec.args))">
              <svg viewBox="0 0 24 24" width="10" height="10" stroke="currentColor" stroke-width="2.5" fill="none">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg>
              <span class="copy-label">{{ copyState['args'] ? 'Copied' : 'Copy' }}</span>
            </button>
          </div>
          <pre class="json-code"><code v-html="highlightJson(formatJson(exec.args))"></code></pre>
        </div>
      </div>

      <!-- 错误状态 -->
      <div class="tool-exec-section is-error" v-if="exec.status === 'error' && exec.error">
        <div class="section-label">Error Output</div>
        <div class="error-text">{{ exec.error }}</div>
      </div>

      <!-- 正常返回结果 -->
      <div class="tool-exec-section" v-if="exec.status === 'success' && exec.result">
        <div class="ide-code-container">
          <div class="ide-code-header">
            <div class="mac-control-dots">
              <span class="dot close"></span>
              <span class="dot minimize"></span>
              <span class="dot expand"></span>
            </div>
            <span class="ide-tab-title">response.log</span>
            <button class="ide-copy-btn" :class="{ copied: copyState['result'] }" @click="handleCopy('result', formatJson(exec.result))">
              <svg viewBox="0 0 24 24" width="10" height="10" stroke="currentColor" stroke-width="2.5" fill="none">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg>
              <span class="copy-label">{{ copyState['result'] ? 'Copied' : 'Copy' }}</span>
            </button>
          </div>
          <pre class="json-code"><code v-html="highlightJson(formatJson(exec.result))"></code></pre>
        </div>
      </div>

      <!-- 💡 顶奢级审批交互面板：磨砂拟态、渐变霓虹呼吸边框与对称排版 -->
      <div class="approval-action-block" v-if="isThisWaitingApproval" @click.stop>
        <div class="approval-message">
          <svg class="warning-icon animate-pulse" viewBox="0 0 24 24" width="14" height="14" stroke="var(--warning-amber)" stroke-width="2" fill="none">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
            <line x1="12" y1="9" x2="12" y2="13"></line>
            <line x1="12" y1="17" x2="12.01" y2="17"></line>
          </svg>
          <span class="warning-text">安全拦截：该工具操作包含副作用，需要您的授权。</span>
        </div>

        <div class="approval-buttons-row">
          <!-- 拒绝按钮 -->
          <button 
            class="approval-btn reject-btn" 
            :disabled="isProcessingApproval"
            @click="emit('reject')"
          >
            <span class="btn-hover-glow"></span>
            <span class="btn-text">拒绝 (Reject)</span>
          </button>

          <!-- 全部授权自动运行 -->
          <button 
            class="approval-btn approve-all-btn" 
            :disabled="isProcessingApproval"
            @click="emit('approve-all')"
            title="将权限配置切换为 Full-Auto，本次运行不再拦截任何工具"
          >
            <span class="btn-hover-glow"></span>
            <span class="btn-text">全部授权 (Full Auto)</span>
          </button>

          <!-- 授权单次运行 -->
          <button 
            class="approval-btn approve-btn" 
            :disabled="isProcessingApproval"
            @click="emit('approve')"
          >
            <span class="btn-hover-glow"></span>
            <span class="btn-text">批准 (Approve)</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* ── 工具调用卡片样式 ── */
.tool-exec-card {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  margin-bottom: 6px;
  position: relative;
  width: 100%;
}

body.theme-default .tool-exec-card,
body.theme-cyberpunk .tool-exec-card,
body.theme-emerald .tool-exec-card,
body.theme-amber .tool-exec-card {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
}

.tool-exec-card:hover {
  background: transparent !important;
}

body.theme-default .tool-exec-card:hover,
body.theme-cyberpunk .tool-exec-card:hover,
body.theme-emerald .tool-exec-card:hover,
body.theme-amber .tool-exec-card:hover {
  background: transparent !important;
}

.tool-exec-card.is-expanded {
  background: transparent !important;
  box-shadow: none !important;
}

body.theme-default .tool-exec-card.is-expanded,
body.theme-cyberpunk .tool-exec-card.is-expanded,
body.theme-emerald .tool-exec-card.is-expanded,
body.theme-amber .tool-exec-card.is-expanded {
  background: transparent !important;
  box-shadow: none !important;
}

.tool-exec-card.has-error {
  background: transparent !important;
}

.tool-exec-card.has-error:hover {
  background: transparent !important;
}

.tool-exec-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 0;
  cursor: pointer;
  user-select: none;
  position: relative;
}

/* 左侧发光指示线 - 隐藏以求极致自然扁平 */
.tool-status-bar {
  display: none;
}

.tool-exec-icon-box {
  width: 22px;
  height: 22px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: transparent !important;
  border: none !important;
  position: relative;
  transition: all 0.2s ease;
}

body.theme-default .tool-exec-icon-box,
body.theme-cyberpunk .tool-exec-icon-box,
body.theme-emerald .tool-exec-icon-box,
body.theme-amber .tool-exec-icon-box {
  background: transparent !important;
  border: none !important;
}

.tool-exec-icon-box.status-success {
  background: transparent !important;
}

.tool-exec-icon-box.status-running {
  background: transparent !important;
}

.tool-exec-icon-box.status-error {
  background: transparent !important;
}

.tool-exec-name {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-primary);
  font-family: var(--font-mono, monospace);
  flex: 1;
}

/* 风趣幽默的展示文字样式覆盖 */
.cute-status-text {
  font-family: var(--font-sans), system-ui, -apple-system, sans-serif !important;
  font-size: 13px !important;
  font-weight: 500 !important;
  letter-spacing: 0px !important;
  color: var(--text-secondary);
  text-transform: none !important;
  transition: color 0.2s ease;
}

.cute-status-text:hover {
  color: var(--text-primary);
}

.cute-status-text.status-error {
  color: var(--danger, #ff453a) !important;
}

.cute-emoji-icon {
  font-size: 13px;
  line-height: 1;
}

.running-indicator {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: var(--accent-emerald, #34c759);
  box-shadow: 0 0 8px var(--accent-emerald, #34c759);
  animation: pulse 1.6s infinite ease-in-out;
}

.tool-exec-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.status-error-label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  color: var(--danger, #ff453a);
  background: rgba(255, 69, 58, 0.12);
  padding: 1px 5px;
  border-radius: 4px;
  font-family: var(--font-mono, monospace);
}

.duration-label {
  font-size: 11px;
  color: var(--text-muted);
  font-family: var(--font-mono, monospace);
}

.header-chevron-btn {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  border-radius: 4px;
  transition: all 0.2s ease;
  outline: none;
}

.header-chevron-btn:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.toggle-chevron {
  transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.toggle-chevron.open {
  transform: rotate(180deg);
}

.tool-exec-body {
  border-top: none !important;
  padding: 4px 0 10px 34px;
  background: transparent !important;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

body.theme-default .tool-exec-body,
body.theme-cyberpunk .tool-exec-body,
body.theme-emerald .tool-exec-body,
body.theme-amber .tool-exec-body {
  background: transparent !important;
  border-top-color: transparent !important;
}

.tool-exec-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.section-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--text-muted);
  letter-spacing: 0.05em;
}

/* --- 💻 HIGH-END macOS IDE CODE CONTAINER --- */
.ide-code-container {
  display: flex;
  flex-direction: column;
  background: #0b0b0e !important;
  border: none !important;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: none !important;
}

.ide-code-header {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  background: #121217 !important;
  border-bottom: 1px solid rgba(255, 255, 255, 0.04);
  user-select: none;
}

.mac-control-dots {
  display: flex;
  gap: 5px;
  align-items: center;
  margin-right: 14px;
}

.mac-control-dots .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
  opacity: 0.85;
}

.mac-control-dots .dot.close { background-color: #ff5f56; }
.mac-control-dots .dot.minimize { background-color: #ffbd2e; }
.mac-control-dots .dot.expand { background-color: #27c93f; }

.ide-tab-title {
  font-size: 10px;
  font-weight: 500;
  font-family: var(--font-mono, monospace);
  color: rgba(255, 255, 255, 0.35);
  letter-spacing: 0.5px;
  text-transform: lowercase;
}

.ide-copy-btn {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 4px;
  background: transparent;
  border: none;
  cursor: pointer;
  color: rgba(255, 255, 255, 0.35);
  transition: all 0.2s ease;
  font-size: 10px;
  font-family: var(--font-sans);
  outline: none;
  padding: 2px 6px;
  border-radius: 4px;
}

.ide-copy-btn:hover {
  color: rgba(255, 255, 255, 0.85);
  background: rgba(255, 255, 255, 0.05);
}

.ide-copy-btn.copied {
  color: var(--accent-emerald, #34c759);
}

.json-code {
  margin: 0;
  padding: 12px 14px;
  background: transparent !important;
  font-size: 11px;
  line-height: 1.6;
  color: #c9d1d9 !important; /* Elegant light text on obsidian backdrop */
  font-family: var(--font-mono, monospace);
  overflow-x: auto;
  max-height: 320px;
  white-space: pre-wrap;
  word-break: break-all;
}

.json-code code {
  color: inherit !important;
  background: transparent !important;
}

/* --- Soft high-fidelity syntax colors --- */
.json-code :deep(.json-key) {
  color: #82aaff !important; /* Soft Pale Blue */
  font-weight: 500;
}
.json-code :deep(.json-string) {
  color: #c3e88d !important; /* Soft Pastel Green */
}
.json-code :deep(.json-number) {
  color: #f78c6c !important; /* Soft Pastel Orange */
}
.json-code :deep(.json-boolean) {
  color: #ffcb6b !important; /* Soft Pale Yellow */
}
.json-code :deep(.json-null) {
  color: #9CA3AF !important;
}

.error-text {
  padding: 10px 12px;
  background: rgba(255, 69, 58, 0.06);
  border: 1px solid rgba(255, 69, 58, 0.15);
  border-radius: 6px;
  font-size: 11px;
  line-height: 1.6;
  color: #ff453a;
  font-family: var(--font-mono, monospace);
  white-space: pre-wrap;
  word-break: break-all;
}

.tool-exec-group-summary {
  cursor: default;
  opacity: 0.75;
}

.tool-exec-group-summary .tool-exec-header {
  cursor: default;
}

.group-count-badge {
  margin-left: 6px;
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  background: rgba(255, 255, 255, 0.06);
  padding: 1px 6px;
  border-radius: 10px;
  letter-spacing: 0.02em;
  flex-shrink: 0;
}

/* ── 顶奢审批操作区样式 ── */
.approval-action-block {
  margin-top: 12px;
  padding: 16px;
  border-radius: 8px;
  background: rgba(251, 191, 36, 0.04);
  border: 1px solid rgba(251, 191, 36, 0.15);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
  position: relative;
  overflow: hidden;
  animation: cardPulseBorder 3s infinite ease-in-out;
}

.is-awaiting-approval {
  border-color: rgba(251, 191, 36, 0.3) !important;
  box-shadow: 0 0 12px rgba(251, 191, 36, 0.1) !important;
}

.approval-pulse-badge {
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 600;
  color: var(--warning-amber, #FBBF24);
  background: rgba(251, 191, 36, 0.12);
  padding: 2px 8px;
  border-radius: 10px;
  margin-left: 8px;
  display: flex;
  align-items: center;
  gap: 6px;
  letter-spacing: 0.5px;
}

.pulse-dot-amber {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--warning-amber, #FBBF24);
  box-shadow: 0 0 8px var(--warning-amber, #FBBF24);
  animation: dotPulse 1.6s infinite ease-in-out;
}

.approval-message {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.warning-text {
  font-size: 12px;
  color: var(--text-secondary);
}

.warning-icon {
  animation: pulse 2s infinite ease-in-out;
}

.approval-buttons-row {
  display: flex;
  gap: 8px;
  width: 100%;
}

.approval-btn {
  flex: 1;
  border: none;
  cursor: pointer;
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 11px;
  font-family: var(--font-mono);
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.approval-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-hover-glow {
  position: absolute;
  top: 0;
  left: -100%;
  width: 300%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.1), transparent);
  transition: all 0.6s ease;
}

.approval-btn:hover:not(:disabled) .btn-hover-glow {
  left: 100%;
}

.approval-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.approval-btn:active:not(:disabled) {
  transform: translateY(0);
}

/* 拒绝按钮 */
.reject-btn {
  background: rgba(239, 68, 68, 0.1);
  color: #EF4444;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.reject-btn:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.2);
  box-shadow: 0 0 12px rgba(239, 68, 68, 0.25);
  border-color: rgba(239, 68, 68, 0.5);
}

/* 全部授权按钮 */
.approve-all-btn {
  background: rgba(16, 185, 129, 0.05);
  color: var(--text-secondary);
  border: 1px solid var(--border-dim);
}

.approve-all-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-primary);
  border-color: var(--text-muted);
}

/* 批准单次运行按钮 */
.approve-btn {
  background: rgba(16, 185, 129, 0.15);
  color: #10B981;
  border: 1px solid rgba(16, 185, 129, 0.35);
  box-shadow: 0 0 10px rgba(16, 185, 129, 0.1);
}

.approve-btn:hover:not(:disabled) {
  background: rgba(16, 185, 129, 0.25);
  box-shadow: 0 0 15px rgba(16, 185, 129, 0.35);
  border-color: rgba(16, 185, 129, 0.6);
}

@keyframes dotPulse {
  0%, 100% {
    transform: scale(0.9);
    opacity: 0.6;
    box-shadow: 0 0 4px rgba(251, 191, 36, 0.4);
  }
  50% {
    transform: scale(1.15);
    opacity: 1;
    box-shadow: 0 0 10px rgba(251, 191, 36, 0.8);
  }
}

@keyframes cardPulseBorder {
  0%, 100% {
    border-color: rgba(251, 191, 36, 0.15);
  }
  50% {
    border-color: rgba(251, 191, 36, 0.35);
    box-shadow: 0 4px 22px rgba(251, 191, 36, 0.05);
  }
}

@keyframes pulse {
  0%, 100% { opacity: 0.8; }
  50% { opacity: 1; }
}
</style>
