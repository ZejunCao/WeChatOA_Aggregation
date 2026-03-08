// ─────────────────────────────────────────────────────────────────────────────
// 路由配置
// 定义 URL 路径和页面组件的对应关系。
// 使用 Hash 模式（URL 中带 #），无需服务器配置，适合本地静态部署。
// ─────────────────────────────────────────────────────────────────────────────

import { createRouter, createWebHashHistory } from 'vue-router'
import FeedView from '@/views/FeedView.vue'
import ConfigView from '@/views/ConfigView.vue'
import LogView from '@/views/LogView.vue'

const router = createRouter({
  // createWebHashHistory：URL 形如 http://localhost:5173/#/config
  // 好处：刷新页面不会 404，不依赖服务器路由配置
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',         // 默认首页：文章信息流
      name: 'feed',
      component: FeedView,
    },
    {
      path: '/config',   // 公众号管理页：添加/删除/爬取/清理
      name: 'config',
      component: ConfigView,
    },
    {
      path: '/logs',     // 操作日志页：查看历史爬取、清理记录
      name: 'logs',
      component: LogView,
    },
  ],
})

export default router
