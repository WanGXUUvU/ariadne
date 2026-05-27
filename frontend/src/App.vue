<script setup lang="ts">
import { onMounted } from 'vue';

onMounted(() => {
  // 读取本地缓存主题并应用到 body 元素
  const savedTheme = localStorage.getItem('agent-build-theme') || 'default';
  document.body.className = `theme-${savedTheme}`;
});
</script>

<template>
  <router-view />
</template>

<style>
/* 可以在此处添加全局路由过渡效果或通用样式 */
</style>
