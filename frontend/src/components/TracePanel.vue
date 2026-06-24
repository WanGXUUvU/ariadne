<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import type { TraceRunSummary } from '../types';

const props = defineProps<{
  runs: TraceRunSummary[];
  isLoading?: boolean;
}>();

const scrollContainer = ref<HTMLElement | null>(null);

const totalEvents = computed(() =>
  props.runs.reduce((count, run) => count + (run.events?.length ?? 0), 0)
);

const formatRunId = (runId: string) => `#${runId.slice(-8).toUpperCase()}`;

const formatClock = (value: string) =>
  new Date(value).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });

const previewText = (value: string, maxLen = 96) => {
  const text = value.replace(/\s+/g, ' ').trim();
  if (text.length <= maxLen) {
    return text;
  }
  return `${text.slice(0, maxLen - 1)}…`;
};

watch(
  () => [props.runs.length, props.isLoading],
  async () => {
    await nextTick();
    if (scrollContainer.value) {
      scrollContainer.value.scrollTop = scrollContainer.value.scrollHeight;
    }
  }
);
</script>

<template>
  <aside class="trace-panel">
    <header class="panel-header trace-header">
      <div class="trace-header-left">
        <span class="mono-label">EXECUTION_TRACE</span>
        <span class="trace-subtitle">Grouped by run_id</span>
      </div>
      <div class="trace-header-stats">
        <span class="trace-stat">{{ runs.length }} RUNS</span>
        <span class="trace-stat">{{ totalEvents }} EVENTS</span>
      </div>
    </header>

    <div class="trace-content" ref="scrollContainer">
      <div v-if="isLoading && runs.length === 0" class="trace-empty">
        <div class="trace-orb trace-orb-loading"></div>
        <div class="mono-label" style="color: var(--text-secondary); margin-bottom: 4px;">REFRESHING TRACE</div>
        <div style="font-size: 12px; color: var(--text-muted);">Loading grouped runs and execution steps.</div>
      </div>

      <div v-else-if="runs.length === 0" class="trace-empty">
        <div class="trace-orb"></div>
        <div class="mono-label" style="color: var(--text-secondary); margin-bottom: 4px;">AWAITING TRACE DATA</div>
        <div style="font-size: 12px; color: var(--text-muted);">Each run will appear as a separate card here.</div>
      </div>

      <div v-else class="run-list">
        <article
          v-for="(run, runIdx) in runs"
          :key="run.run_id"
          class="run-card"
          :class="{ latest: runIdx === runs.length - 1 }"
        >
          <div class="run-card-top">
            <div class="run-id-block">
              <div class="run-badge">RUN {{ String(runIdx + 1).padStart(2, '0') }}</div>
              <div class="run-id">{{ formatRunId(run.run_id) }}</div>
            </div>

            <div class="run-meta">
              <span class="meta-pill">{{ run.event_count }} EVENTS</span>
              <span v-if="run.agent_name" class="meta-pill">{{ run.agent_name }}</span>
              <span v-if="run.skill_name" class="meta-pill">{{ run.skill_name }}</span>
            </div>
          </div>

          <div class="run-times">
            <span>START {{ formatClock(run.created_at) }}</span>
            <span v-if="run.finished_at">END {{ formatClock(run.finished_at) }}</span>
          </div>

          <div class="run-section">
            <div class="section-label">USER INPUT</div>
            <div class="section-text">{{ previewText(run.user_input, 140) }}</div>
          </div>

          <div class="run-section">
            <div class="section-label">REPLY</div>
            <div class="section-text reply-text">{{ previewText(run.reply || 'No reply returned') }}</div>
          </div>

          <div class="timeline">
            <div class="timeline-label">EVENT TIMELINE</div>
            <div class="timeline-list">
              <div
                v-for="event in run.events"
                :key="`${run.run_id}-${event.index}-${event.type}`"
                class="event-item"
                :class="event.type"
              >
                <div class="event-meta">
                  <span class="event-index">[{{ String(event.index).padStart(3, '0') }}]</span>
                  <span class="event-type">{{ event.type.replace(/_/g, ' ').toUpperCase() }}</span>
                </div>

                <div v-if="event.type === 'assistant_tool_call'" class="event-payload">
                  <div class="tool-name">
                    <svg viewBox="0 0 24 24" width="14" height="14" stroke="var(--accent)" stroke-width="2" fill="none" style="margin-right:6px">
                      <polyline points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polyline>
                    </svg>
                    {{ event.tool_name }}
                    <span style="color:var(--text-muted); font-size: 11px;">#{{ event.tool_call_id }}</span>
                  </div>
                  <pre v-if="event.content" class="payload-code">{{ event.content }}</pre>
                </div>

                <div v-else-if="event.type === 'tool_result'" class="event-payload">
                  <div v-if="event.tool_result?.ok">
                    <div class="result-label ok">✓ RESULT OK</div>
                    <pre v-if="event.tool_result.content" class="payload-code success">{{ event.tool_result.content }}</pre>
                  </div>
                  <div v-else-if="event.tool_result?.error">
                    <div class="result-label error">✗ ERROR: {{ event.tool_result.error.code }}</div>
                    <pre class="payload-code error">{{ event.tool_result.error.message }}</pre>
                  </div>
                </div>

                <div v-else-if="event.type === 'tool_error'" class="event-payload">
                  <div class="result-label error">✗ EXECUTION ERROR</div>
                  <pre class="payload-code error">{{ event.content }}</pre>
                </div>

                <div v-else-if="event.type === 'final_answer'" class="event-payload">
                  <div class="result-label final">→ FINAL ANSWER</div>
                  <div class="payload-text">{{ event.content }}</div>
                </div>
              </div>
            </div>
          </div>
        </article>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.trace-panel {
  display: flex;
  flex-direction: column;
  background: rgba(var(--bg-panel-rgb, 10, 10, 10), 0.3) !important;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border-left: 1px solid var(--border-dim);
  height: 100%;
}

.trace-header {
  gap: 12px;
}

.trace-header-left {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.trace-subtitle {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  text-transform: uppercase;
}

.trace-header-stats {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.trace-stat,
.meta-pill {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-secondary);
  border: 1px solid var(--border-dim);
  background: rgba(255, 255, 255, 0.03);
  border-radius: 999px;
  padding: 5px 8px;
}

.trace-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 18px;
  overflow-y: auto;
}

.trace-empty {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  border: 1px dashed var(--border-dim);
  border-radius: var(--radius-sm);
  padding: 28px 20px;
  background: rgba(255, 255, 255, 0.02);
}

.trace-orb {
  width: 42px;
  height: 42px;
  border-radius: 999px;
  margin-bottom: 14px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  background:
    radial-gradient(circle at 35% 35%, rgba(255, 255, 255, 0.35), transparent 45%),
    rgba(255, 255, 255, 0.04);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.03);
}

.trace-orb-loading {
  animation: pulseOrb 1.2s ease-in-out infinite;
}

.run-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.run-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border-radius: 12px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.045), rgba(255, 255, 255, 0.02)),
    var(--bg-app);
  border: 1px solid var(--border-dim);
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.18);
  overflow: hidden;
  animation: traceSlideIn 0.25s ease both;
}

.run-card::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  background: linear-gradient(180deg, var(--accent), color-mix(in srgb, var(--accent) 15%, transparent));
  opacity: 0.75;
}

.run-card.latest {
  border-color: color-mix(in srgb, var(--accent) 30%, transparent);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--accent) 6%, transparent), 0 18px 40px rgba(0, 0, 0, 0.26);
}

.run-card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.run-id-block {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.run-badge {
  width: fit-content;
  padding: 6px 8px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.08em;
}

.run-id {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  color: var(--text-muted);
}

.run-meta {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.run-times {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  text-transform: uppercase;
}

.run-section {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.section-label,
.timeline-label {
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.1em;
  color: var(--text-muted);
  text-transform: uppercase;
}

.section-text {
  color: var(--text-primary);
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.reply-text {
  color: #d9d9d9;
}

.timeline {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.timeline-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.event-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid var(--border-dim);
  font-family: var(--font-mono);
  font-size: 12px;
  transition: var(--transition-fast);
}

.event-item:hover {
  background: var(--bg-hover);
  border-color: var(--border-strong);
}

.event-item.assistant_tool_call {
  border-left: 2px solid var(--accent);
}

.event-item.tool_result {
  border-left: 2px solid var(--success);
}

.event-item.tool_error {
  border-left: 2px solid var(--danger);
}

.event-item.final_answer {
  border-left: 2px solid var(--text-primary);
}

.event-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-muted);
  font-size: 10px;
}

.event-type {
  font-weight: 600;
  letter-spacing: 0.06em;
}

.event-payload {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.tool-name {
  display: flex;
  align-items: center;
  color: var(--text-primary);
  font-weight: 500;
}

.payload-code {
  margin: 0;
  padding: 10px 12px;
  background: rgba(255, 255, 255, 0.04);
  border-radius: 8px;
  border: 1px solid var(--border-dim);
  color: var(--text-secondary);
  font-size: 11px;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 240px;
  overflow-y: auto;
}

.payload-code.success {
  color: var(--success);
  border-color: color-mix(in srgb, var(--success) 20%, transparent);
  background: color-mix(in srgb, var(--success) 5%, transparent);
}

.payload-code.error {
  color: var(--danger);
  border-color: color-mix(in srgb, var(--danger) 20%, transparent);
  background: color-mix(in srgb, var(--danger) 5%, transparent);
}

.payload-text {
  color: var(--text-secondary);
  line-height: 1.5;
  white-space: pre-wrap;
}

.result-label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.result-label.ok {
  color: var(--success);
}

.result-label.error {
  color: var(--danger);
}

.result-label.final {
  color: var(--accent);
}

@keyframes traceSlideIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes pulseOrb {
  0% {
    transform: scale(1);
    opacity: 0.8;
  }
  50% {
    transform: scale(1.08);
    opacity: 1;
  }
  100% {
    transform: scale(1);
    opacity: 0.8;
  }
}

</style>
