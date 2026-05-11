<script setup lang="ts">
import { ref, watch } from 'vue';
import type { AgentEvent } from '../types';

const props = defineProps<{
  events: AgentEvent[];
  autoExpand?: boolean;   // live 模式下传 true，自动展开
}>();

const expanded = ref(props.autoExpand ?? false);

// autoExpand 变成 false（streaming 结束后）时不自动折叠，保留用户当前状态
watch(() => props.autoExpand, (val) => {
  if (val) expanded.value = true;
});

const eventIcon = (event: AgentEvent) => {
  if (event.type === 'assistant_tool_call') return '🔧';
  if (event.type === 'tool_result') return '✅';
  if (event.type === 'tool_error') return '❌';
  if (event.type === 'final_answer') return '💬';
  return '·';
};

const eventLabel = (event: AgentEvent) => {
  if (event.type === 'assistant_tool_call') return event.tool_name ?? 'tool';
  if (event.type === 'tool_result') return event.tool_name ? `${event.tool_name} 返回` : '工具返回';
  if (event.type === 'tool_error') return event.tool_name ? `${event.tool_name} 出错` : '工具出错';
  if (event.type === 'final_answer') return '最终回答';
  return event.type;
};

// 展示 event content 的摘要（最多 80 字符）
const truncate = (s: string | null | undefined, max = 80) => {
  if (!s) return '';
  const oneLine = s.replace(/\n/g, ' ');
  return oneLine.length > max ? oneLine.slice(0, max) + '…' : oneLine;
};
</script>

<template>
  <div class="trace-inline">
    <!-- 折叠/展开按钮 -->
    <button class="trace-toggle" @click="expanded = !expanded">
      <span class="trace-toggle-arrow" :class="{ open: expanded }">›</span>
      <span class="trace-toggle-label mono-label">
        运行过程
      </span>
      <span class="trace-toggle-count mono-label">
        {{ events.length }} 步
      </span>
    </button>

    <!-- 事件列表，用 CSS max-height 做弹簧动画 -->
    <div class="trace-body" :class="{ open: expanded }">
      <div class="trace-events">
        <div
          v-for="event in events"
          :key="event.index"
          class="trace-event"
          :class="`event-${event.type}`"
        >
          <span class="event-icon">{{ eventIcon(event) }}</span>
          <span class="event-label mono-label">{{ eventLabel(event) }}</span>
          <span v-if="event.content" class="event-content">
            {{ truncate(event.content) }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.trace-inline {
  margin-top: 10px;
  border: 1px solid var(--border-dim);
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--bg-app);
}

/* 折叠按钮行 */
.trace-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
  text-align: left;
  transition: background 0.15s;
}

.trace-toggle:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.trace-toggle-arrow {
  font-size: 14px;
  line-height: 1;
  display: inline-block;
  transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  transform: rotate(0deg);
  color: var(--text-muted);
}

.trace-toggle-arrow.open {
  transform: rotate(90deg);
}

.trace-toggle-label {
  flex: 1;
  font-size: 10px;
  letter-spacing: 0.05em;
}

.trace-toggle-count {
  font-size: 10px;
  color: var(--text-muted);
}

/* 事件列表容器 — 弹簧展开动画 */
.trace-body {
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.35s cubic-bezier(0.4, 0, 0.2, 1),
              opacity 0.25s ease;
  opacity: 0;
}

.trace-body.open {
  max-height: 320px;   /* 限制高度，内容超出时可滚动 */
  overflow-y: auto;
  opacity: 1;
}

.trace-events {
  border-top: 1px solid var(--border-dim);
  padding: 6px 0;
}

/* 单条事件 */
.trace-event {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 5px 12px;
  font-size: 12px;
  border-bottom: 1px solid var(--border-dim);
  transition: background 0.1s;
}

.trace-event:last-child {
  border-bottom: none;
}

.trace-event:hover {
  background: var(--bg-hover);
}

.event-icon {
  flex-shrink: 0;
  font-size: 12px;
  line-height: 1;
}

.event-label {
  flex-shrink: 0;
  font-size: 10px;
  color: var(--text-primary);
  min-width: 90px;
}

.event-content {
  color: var(--text-muted);
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 320px;
  font-family: var(--font-mono, monospace);
}

/* 不同事件类型的左侧色条 */
.event-assistant_tool_call {
  border-left: 2px solid var(--accent);
  padding-left: 10px;
}

.event-tool_result {
  border-left: 2px solid #50E3C2;
  padding-left: 10px;
}

.event-tool_error {
  border-left: 2px solid #E35050;
  padding-left: 10px;
}

.event-final_answer {
  border-left: 2px solid var(--text-muted);
  padding-left: 10px;
}
</style>
