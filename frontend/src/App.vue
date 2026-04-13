<script setup lang="ts">
import { computed } from 'vue';
import { RouterLink, RouterView, useRoute } from 'vue-router';

const route = useRoute();

const navItems = [
  { to: '/', label: '首页' },
  { to: '/sites', label: '站点管理' },
  { to: '/articles', label: '新闻列表' },
];

const activePath = computed(() => route.path);
</script>

<template>
  <div class="app-layout">
    <header class="app-header">
      <div class="app-brand">
        <strong>AI News Spider</strong>
        <span>Frontend Console</span>
      </div>
      <nav class="app-nav">
        <RouterLink
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="app-nav-link"
          :class="{ active: activePath === item.to }"
        >
          {{ item.label }}
        </RouterLink>
      </nav>
    </header>
    <div class="app-content">
      <RouterView />
    </div>
  </div>
</template>
