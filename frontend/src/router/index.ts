import { createRouter, createWebHashHistory } from 'vue-router'
import FeedView from '@/views/FeedView.vue'
import ConfigView from '@/views/ConfigView.vue'
import LogView from '@/views/LogView.vue'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      name: 'feed',
      component: FeedView,
    },
    {
      path: '/config',
      name: 'config',
      component: ConfigView,
    },
    {
      path: '/logs',
      name: 'logs',
      component: LogView,
    },
  ],
})

export default router
