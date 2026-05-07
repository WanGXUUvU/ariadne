<script setup lang="ts">
defineProps<{
  eventCount: number;
}>();
</script>

<template>
  <aside class="trace-panel">
    <header class="panel-header">
      <span class="mono-label">EXECUTION_TRACE</span>
      <span class="mono-label">{{ eventCount }} EVENTS</span>
    </header>
    
    <div class="trace-content">
      <div class="trace-empty">
        <svg viewBox="0 0 24 24" width="24" height="24" stroke="var(--text-muted)" stroke-width="1.5" fill="none" style="margin-bottom: 12px;"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg>
        <div class="mono-label" style="color: var(--text-secondary); margin-bottom: 4px;">AWAITING TRACE DATA</div>
        <div style="font-size: 12px; color: var(--text-muted);">Real-time execution logs will appear here.</div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.trace-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 24px;
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
</style>
