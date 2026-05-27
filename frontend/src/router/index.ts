import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      redirect: '/coding'
    },
    {
      path: '/coding',
      name: 'Coding',
      component: () => import('../views/CodingView.vue')
    },
    {
      path: '/assistant',
      name: 'Assistant',
      component: () => import('../views/AssistantView.vue')
    }
  ]
})

export default router
