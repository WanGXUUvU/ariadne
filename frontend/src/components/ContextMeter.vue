<script setup lang="ts">
/**
 * ContextMeter.vue
 * 职责：展示当前 session 的上下文窗口用量，含分类占比（估算）和压缩按钮。
 * 不负责：实际压缩逻辑（通过 emit('compact') 向上抛）
 *
 * 输入：
 *   - contextTokens: 当前已用令牌数（来自 session.context_tokens）
 *   - contextLength:  模型最大上下文长度（来自 model_settings，默认 128000）
 *   - messageCount:   当前消息数（用于估算分类占比）
 *   - isCompacting:   压缩进行中
 *
 * 输出：emit('compact') → 父组件触发压缩
 */
import { computed } from 'vue';

const props = withDefaults(defineProps<{
  contextTokens: number;
  contextLength: number;
  messageCount: number;
  isCompacting: boolean;
  isLoading: boolean;
}>(), {
  contextTokens: 0,
  contextLength: 128000,
  messageCount: 0,
  isCompacting: false,
  isLoading: false,
});

const emit = defineEmits<{
  (e: 'compact'): void;
}>();

// ── 计算用量百分比 ──────────────────────────────────────────────────
const usedPct = computed(() => {
  if (!props.contextLength) return 0;
  return Math.min(100, (props.contextTokens / props.contextLength) * 100);
});

// 保留用于响应的比例（Claude 等通常 10-20%）
const RESERVE_PCT = 15;

// 总已用百分比（用于进度条颜色判断）
const usedColor = computed(() => {
  if (usedPct.value > 80) return '#ff453a';
  if (usedPct.value > 60) return '#f5a623';
  return 'var(--accent-blue, #3b82f6)';
});

// ── 分类占比（估算）────────────────────────────────────────────────
// 规则：把已用 token 总量按比例分配到各分类，这是近似值
// System Instructions ≈ 3-4%   Tool Definitions ≈ 8-12%
// Messages ≈ 剩余的 70%        Tool Results ≈ 剩余的 30%
const breakdown = computed(() => {
  const total = props.contextTokens;
  if (total === 0) return null;
  const ctxTotal = props.contextLength;

  const sysInstr = Math.round(total * 0.033);
  const toolDefs  = Math.round(total * 0.087);
  const msgs      = Math.round(total * 0.61);
  const toolRes   = Math.round(total * 0.27);

  const pct = (n: number) =>
    ctxTotal ? `${((n / ctxTotal) * 100).toFixed(1)}%` : '—';

  return [
    { section: 'System', items: [
      { label: 'System Instructions', tokens: sysInstr, pct: pct(sysInstr) },
      { label: 'Tool Definitions',    tokens: toolDefs,  pct: pct(toolDefs)  },
    ]},
    { section: 'User Context', items: [
      { label: 'Messages',     tokens: msgs,    pct: pct(msgs)    },
      { label: 'Tool Results', tokens: toolRes, pct: pct(toolRes) },
    ]},
  ];
});

// ── 格式化 token 数 ──────────────────────────────────────────────────
function fmtTokens(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return String(n);
}
</script>

<template>
  <div class="ctx-meter">
    <!-- 标题 -->
    <div class="ctx-title">上下文窗口</div>

    <!-- 主用量行 -->
    <div class="ctx-usage-row">
      <span class="ctx-count">
        {{ fmtTokens(contextTokens) }}/{{ fmtTokens(contextLength) }} 个令牌
      </span>
      <span class="ctx-pct">{{ usedPct.toFixed(0) }}%</span>
    </div>

    <!-- 进度条：已用 + 保留区 -->
    <div class="ctx-bar-track">
      <div
        class="ctx-bar-used"
        :style="{ width: `${Math.max(0, usedPct - RESERVE_PCT)}%`, background: usedColor }"
      />
      <div
        class="ctx-bar-reserve"
        :style="{ width: `${Math.min(usedPct, RESERVE_PCT)}%` }"
      />
    </div>

    <!-- 保留标签 -->
    <div class="ctx-reserve-label">
      <svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2.5">
        <line x1="16" y1="8" x2="8" y2="16"/><line x1="8" y1="8" x2="16" y2="16"/>
      </svg>
      保留用于响应
    </div>

    <div v-if="breakdown" class="ctx-breakdown">
      <div
        v-for="group in breakdown"
        :key="group.section"
        class="ctx-group"
      >
        <div class="ctx-group-label">{{ group.section }}</div>
        <div
          v-for="item in group.items"
          :key="item.label"
          class="ctx-row"
        >
          <span class="ctx-row-label">{{ item.label }}</span>
          <span class="ctx-row-pct">{{ item.pct }}</span>
        </div>
      </div>
    </div>

    <!-- 压缩按钮 -->
    <button
      class="ctx-compact-btn"
      :disabled="isCompacting || isLoading"
      @click="emit('compact')"
    >
      <svg v-if="isCompacting" class="ctx-spin" viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none">
        <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
      </svg>
      {{ isCompacting ? '压缩中…' : '压缩对话' }}
    </button>
  </div>
</template>

<style scoped>
.ctx-meter {
  width: 240px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-strong);
  border-radius: 14px;
  padding: 16px 16px 14px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.4), 0 0 0 1px var(--border-dim);
  display: flex;
  flex-direction: column;
  gap: 0;
}

/* 标题 */
.ctx-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 10px;
  letter-spacing: 0.01em;
}

/* 用量行 */
.ctx-usage-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 8px;
}
.ctx-count {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}
.ctx-pct {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  font-family: var(--font-mono, monospace);
}

/* 进度条 */
.ctx-bar-track {
  height: 5px;
  background: var(--bg-active);
  border-radius: 3px;
  overflow: hidden;
  display: flex;
  margin-bottom: 6px;
}
.ctx-bar-used {
  height: 100%;
  border-radius: 3px 0 0 3px;
  transition: width 0.4s ease, background 0.4s ease;
}
.ctx-bar-reserve {
  height: 100%;
  /* 斜线纹理 */
  background: repeating-linear-gradient(
    45deg,
    rgba(59, 130, 246, 0.5),
    rgba(59, 130, 246, 0.5) 2px,
    transparent 2px,
    transparent 5px
  );
  border-radius: 0 3px 3px 0;
  transition: width 0.4s ease;
}

/* 保留标签 */
.ctx-reserve-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10.5px;
  color: rgba(59, 130, 246, 0.7);
  margin-bottom: 14px;
}

/* 分类区域 */
.ctx-breakdown {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 14px;
}

.ctx-group {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.ctx-group-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  margin-bottom: 2px;
}

.ctx-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.ctx-row-label {
  font-size: 12px;
  color: var(--text-secondary);
}
.ctx-row-pct {
  font-size: 11px;
  color: var(--text-muted);
  font-family: var(--font-mono, monospace);
}

/* 压缩按钮 */
.ctx-compact-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  width: 100%;
  padding: 9px 0;
  background: var(--bg-hover);
  border: 1px solid var(--border-dim);
  border-radius: 8px;
  color: var(--text-secondary);
  font-size: 12.5px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s;
}
.ctx-compact-btn:hover:not(:disabled) {
  background: var(--bg-active);
  border-color: var(--border-strong);
  color: var(--text-primary);
}
.ctx-compact-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 旋转动画 */
@keyframes spin {
  to { transform: rotate(360deg); }
}
.ctx-spin {
  animation: spin 1s linear infinite;
}
</style>
