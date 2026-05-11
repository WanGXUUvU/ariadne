<script setup lang="ts">
/**
 * ToolIcons — 工具事件专用图标组件
 *
 * 职责：根据事件类型渲染精致的 SVG 图标
 * 不负责：布局、文字标签、折叠逻辑
 * 输入：type（事件类型字符串）、size（可选，默认 16）
 * 输出：一个 inline SVG 元素
 */
defineProps<{
  type: string;
  size?: number;
}>();
</script>

<template>
  <!-- 工具调用：闪电图标 -->
  <svg
    v-if="type === 'assistant_tool_call'"
    :width="size ?? 16"
    :height="size ?? 16"
    viewBox="0 0 24 24"
    fill="none"
    class="tool-icon icon-call"
  >
    <path
      d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"
      stroke="currentColor"
      stroke-width="1.5"
      stroke-linecap="round"
      stroke-linejoin="round"
      fill="currentColor"
      fill-opacity="0.15"
    />
  </svg>

  <!-- 工具成功返回：圆形对勾 -->
  <svg
    v-else-if="type === 'tool_result'"
    :width="size ?? 16"
    :height="size ?? 16"
    viewBox="0 0 24 24"
    fill="none"
    class="tool-icon icon-result"
  >
    <circle
      cx="12" cy="12" r="10"
      stroke="currentColor"
      stroke-width="1.5"
      fill="currentColor"
      fill-opacity="0.1"
    />
    <path
      d="M8 12.5l2.5 2.5 5-5"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  </svg>

  <!-- 工具出错：圆形叉号 -->
  <svg
    v-else-if="type === 'tool_error'"
    :width="size ?? 16"
    :height="size ?? 16"
    viewBox="0 0 24 24"
    fill="none"
    class="tool-icon icon-error"
  >
    <circle
      cx="12" cy="12" r="10"
      stroke="currentColor"
      stroke-width="1.5"
      fill="currentColor"
      fill-opacity="0.1"
    />
    <path
      d="M15 9l-6 6M9 9l6 6"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
    />
  </svg>

  <!-- 最终回答：对话气泡 -->
  <svg
    v-else-if="type === 'final_answer'"
    :width="size ?? 16"
    :height="size ?? 16"
    viewBox="0 0 24 24"
    fill="none"
    class="tool-icon icon-answer"
  >
    <path
      d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2v10z"
      stroke="currentColor"
      stroke-width="1.5"
      stroke-linecap="round"
      stroke-linejoin="round"
      fill="currentColor"
      fill-opacity="0.1"
    />
  </svg>

  <!-- 兜底：小圆点 -->
  <span v-else class="tool-icon icon-default">•</span>
</template>

<style scoped>
.tool-icon {
  flex-shrink: 0;
  display: inline-flex;
  vertical-align: middle;
}

/* 每种类型对应不同色彩 */
.icon-call   { color: var(--accent-blue, #60A5FA); }
.icon-result { color: var(--accent-emerald, #34D399); }
.icon-error  { color: var(--danger, #FF453A); }
.icon-answer { color: var(--text-secondary, #A1A1AA); }
.icon-default {
  color: var(--text-muted);
  font-size: 14px;
  line-height: 1;
}
</style>
