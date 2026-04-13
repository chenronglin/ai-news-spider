import { createRouter, createWebHistory } from 'vue-router';
import HomeView from '@/views/HomeView.vue';
import ArticleListView from '@/views/ArticleListView.vue';
import SiteManagerView from '@/views/SiteManagerView.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
    },
    {
      path: '/sites',
      name: 'sites',
      component: SiteManagerView,
    },
    {
      path: '/articles',
      name: 'articles',
      component: ArticleListView,
    },
  ],
});

export default router;
