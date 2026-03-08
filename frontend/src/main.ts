// ─────────────────────────────────────────────────────────────────────────────
// 应用入口文件
// 负责创建 Vue 应用实例，挂载插件，并将应用渲染到 index.html 的 #app 节点。
// ─────────────────────────────────────────────────────────────────────────────

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'
import router from './router'
import App from './App.vue'
import './style.css'

// 创建 Pinia 状态管理实例
const pinia = createPinia()
// 添加持久化插件：让 store 中标记了 persist: true 的数据自动同步到 localStorage
// 这样刷新页面后已读状态、收藏、主题偏好等数据不会丢失
pinia.use(piniaPluginPersistedstate)

const app = createApp(App)
app.use(pinia)   // 注册状态管理
app.use(router)  // 注册路由
app.mount('#app') // 挂载到 index.html 中的 <div id="app">
