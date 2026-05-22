<script setup lang="ts">
/**
 * ToolIcons — 工具事件及特定工具名称专用线性图标组件
 *
 * 职责：渲染精致的 1.5px Stroke/Outline SVG 图标，端点/连接处均为圆角，不含大面积填充
 * 不负责：外层圆角背景、边距、动画
 * 输入：type（事件类型或工具名称）、size（可选，默认 14）
 */
defineProps<{
  type: string;
  size?: number;
}>();
</script>

<template>
  <!-- 1. 文件夹/目录树图标：针对 fs_list 或 list_dir 等 -->
  <svg
    v-if="type === 'fs_list' || type === 'list_dir' || type === 'directory' || type.includes('folder')"
    :width="size ?? 14"
    :height="size ?? 14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.5"
    stroke-linecap="round"
    stroke-linejoin="round"
    class="tool-icon"
  >
    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
  </svg>

  <!-- 2. 文件类图标：针对 fs_read, fs_write, read_file, write_file, file_text -->
  <svg
    v-else-if="type.startsWith('fs_') || type.includes('file') || type.includes('read_url_content')"
    :width="size ?? 14"
    :height="size ?? 14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.5"
    stroke-linecap="round"
    stroke-linejoin="round"
    class="tool-icon"
  >
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
    <line x1="16" y1="13" x2="8" y2="13" />
    <line x1="16" y1="17" x2="8" y2="17" />
  </svg>

  <!-- 3. 网络浏览器/搜索类图标：针对 web_search, search_web -->
  <svg
    v-else-if="type === 'web_search' || type === 'search_web' || type.includes('globe') || type.includes('network') || type.includes('internet')"
    :width="size ?? 14"
    :height="size ?? 14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.5"
    stroke-linecap="round"
    stroke-linejoin="round"
    class="tool-icon"
  >
    <circle cx="12" cy="12" r="10" />
    <line x1="2" y1="12" x2="22" y2="12" />
    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
  </svg>

  <!-- 4. 终端/命令行执行图标：针对 run_command -->
  <svg
    v-else-if="type === 'run_command' || type.includes('terminal') || type.includes('command') || type.includes('execute')"
    :width="size ?? 14"
    :height="size ?? 14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.5"
    stroke-linecap="round"
    stroke-linejoin="round"
    class="tool-icon"
  >
    <polyline points="4 17 10 11 4 5" />
    <line x1="12" y1="19" x2="20" y2="19" />
  </svg>

  <!-- 5. 子 Agent/工作流/衍生图标：针对 spawn_child_agent, define_subagent -->
  <svg
    v-else-if="type.includes('subagent') || type.includes('child_agent') || type === 'spawn_child_agent' || type.includes('workflow') || type.includes('cpu')"
    :width="size ?? 14"
    :height="size ?? 14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.5"
    stroke-linecap="round"
    stroke-linejoin="round"
    class="tool-icon"
  >
    <rect x="3" y="3" width="7" height="7" rx="1" />
    <rect x="14" y="3" width="7" height="7" rx="1" />
    <rect x="14" y="14" width="7" height="7" rx="1" />
    <rect x="3" y="14" width="7" height="7" rx="1" />
    <path d="M10 6.5h4M10 17.5h4M6.5 10v4M17.5 10v4" />
  </svg>

  <!-- 6. 闪电（工具调用发起）：针对 assistant_tool_call -->
  <svg
    v-else-if="type === 'assistant_tool_call'"
    :width="size ?? 14"
    :height="size ?? 14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.5"
    stroke-linecap="round"
    stroke-linejoin="round"
    class="tool-icon"
  >
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
  </svg>

  <!-- 7. 对勾（工具调用成功）：针对 tool_result -->
  <svg
    v-else-if="type === 'tool_result'"
    :width="size ?? 14"
    :height="size ?? 14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.5"
    stroke-linecap="round"
    stroke-linejoin="round"
    class="tool-icon"
  >
    <circle cx="12" cy="12" r="10" />
    <polyline points="12 5 12 12 16 14" />
  </svg>

  <!-- 8. 错误（工具调用失败）：针对 tool_error -->
  <svg
    v-else-if="type === 'tool_error'"
    :width="size ?? 14"
    :height="size ?? 14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.5"
    stroke-linecap="round"
    stroke-linejoin="round"
    class="tool-icon"
  >
    <circle cx="12" cy="12" r="10" />
    <line x1="15" y1="9" x2="9" y2="15" />
    <line x1="9" y1="9" x2="15" y2="15" />
  </svg>

  <!-- 9. 兜底通用工具（画笔）：针对 generic or other tool names -->
  <svg
    v-else
    :width="size ?? 14"
    :height="size ?? 14"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.5"
    stroke-linecap="round"
    stroke-linejoin="round"
    class="tool-icon"
  >
    <path d="M12 20h9" />
    <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
  </svg>
</template>

<style scoped>
.tool-icon {
  flex-shrink: 0;
  display: inline-flex;
  vertical-align: middle;
}
</style>
