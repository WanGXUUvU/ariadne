<script setup lang="ts">
import { ref, watch, nextTick } from 'vue';
import type { AgentEvent } from '../types';

const props = defineProps<{
  events: AgentEvent[];
}>();

const scrollContainer = ref<HTMLElement | null>(null);

watch(() => props.events.length, async () => {
  await nextTick();
  if (scrollContainer.value) {
    scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight;
  }
});
</script>

<template>
  <aside class="trace-panel">
    <header class="panel-header">
      <span class="mono-label">EXECUTION_TRACE</span>
      <span class="mono-label">{{ events.length }} EVENTS</span>
    </header>
    
    <div class="trace-content" ref="scrollContainer">
      <div v-if="events.length === 0" class="trace-empty">
        <svg viewBox="0 0 24 24" width="24" height="24" stroke="var(--text-muted)" stroke-width="1.5" fill="none" style="margin-bottom: 12px;"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg>
        <div class="mono-label" style="color: var(--text-secondary); margin-bottom: 4px;">AWAITING TRACE DATA</div>
        <div style="font-size: 12px; color: var(--text-muted);">Real-time execution logs will appear here.</div>
      </div>
      
      <div v-else class="event-list">
        <div v-for="(event, idx) in events" :key="idx" class="event-item" :class="event.type">
          <div class="event-meta">
            <span class="event-index">[{{ String(event.index).padStart(3, '0') }}]</span>
            <span class="event-type">{{ event.type.replace(/_/g, ' ').toUpperCase() }}</span>
          </div>
          
          <div v-if="event.type === 'assistant_tool_call'" class="event-payload">
            <div class="tool-name">
              <svg viewBox="0 0 24 24" width="14" height="14" stroke="var(--accent)" stroke-width="2" fill="none" style="margin-right:6px"><polyline points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polyline></svg>
              {{ event.tool_name }} <span style="color:var(--text-muted); font-size: 11px;">#{{ event.tool_call_id }}</span>
            </div>
            <pre v-if="event.content" class="payload-code">{{ event.content }}</pre>
          </div>
          
          <div v-else-if="event.type === 'tool_result'" class="event-payload">
            <div v-if="event.tool_result?.ok">
              <div style="color:#50E3C2; margin-bottom: 4px; font-weight:600; font-size:11px;">✓ RESULT OK</div>
              <pre v-if="event.tool_result.content" class="payload-code success">{{ event.tool_result.content }}</pre>
            </div>
            <div v-else-if="event.tool_result?.error">
              <div style="color:#FF453A; margin-bottom: 4px; font-weight:600; font-size:11px;">✗ ERROR: {{ event.tool_result.error.code }}</div>
              <pre class="payload-code error">{{ event.tool_result.error.message }}</pre>
            </div>
          </div>
          
          <div v-else-if="event.type === 'tool_error'" class="event-payload">
             <div style="color:#FF453A; margin-bottom: 4px; font-weight:600; font-size:11px;">✗ EXECUTION ERROR</div>
             <pre class="payload-code error">{{ event.content }}</pre>
          </div>
          
          <div v-else-if="event.type === 'final_answer'" class="event-payload">
             <div style="color:var(--accent); margin-bottom: 4px; font-weight:600; font-size:11px;">→ FINAL ANSWER</div>
             <div class="payload-text">{{ event.content }}</div>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.trace-panel {
  display: flex;
  flex-direction: column;
  background: var(--bg-panel);
  border-left: 1px solid var(--border-dim);
  height: 100%;
}

.panel-header {
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  border-bottom: 1px solid var(--border-dim);
  flex-shrink: 0;
}

.trace-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 24px;
  overflow-y: auto;
}

.trace-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  border: 1px dashed var(--border-dim);
  border-radius: var(--radius-sm);
  padding: 24px;
}

.event-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.event-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  background: var(--bg-app);
  border: 1px solid var(--border-dim);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 13px;
  transition: var(--transition-fast);
  animation: traceSlideIn 0.25s ease both;
}

.event-item:hover {
  background: var(--bg-hover);
  box-shadow: var(--shadow-glow, 0 0 20px rgba(255,255,255,0.03));
}

.event-item.assistant_tool_call { border-left: 2px solid var(--accent); }
.event-item.tool_result { border-left: 2px solid #50E3C2; }
.event-item.tool_error { border-left: 2px solid #FF453A; }
.event-item.final_answer { border-left: 2px solid var(--text-primary); }

.event-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-muted);
  font-size: 11px;
}

.event-type {
  font-weight: 600;
  letter-spacing: 0.05em;
}

.tool-name {
  display: flex;
  align-items: center;
  color: var(--text-primary);
  font-weight: 500;
  margin-bottom: 8px;
}

.payload-code {
  margin: 0;
  padding: 12px;
  background: rgba(255,255,255,0.03);
  border-radius: 4px;
  border: 1px solid var(--border-dim);
  color: var(--text-secondary);
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
}

.payload-code.success { color: #50E3C2; border-color: rgba(80,227,194,0.2); background: rgba(80,227,194,0.05); }
.payload-code.error { color: #FF453A; border-color: rgba(255,69,58,0.2); background: rgba(255,69,58,0.05); }

.payload-text {
  color: var(--text-secondary);
  line-height: 1.5;
  white-space: pre-wrap;
}

@keyframes traceSlideIn {
  from { opacity: 0; transform: translateX(8px); }
  to { opacity: 1; transform: translateX(0); }
}
</style>
