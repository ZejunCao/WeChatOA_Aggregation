import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import fs from 'fs'

export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(),
    {
      name: 'serve-data-files',
      configureServer(server) {
        server.middlewares.use('/data', (req, res, next) => {
          const urlPath = (req.url || '/').replace(/^\//, '')
          const filePath = path.resolve(__dirname, '../data', urlPath)
          if (!fs.existsSync(filePath)) { next(); return }
          if (filePath.endsWith('.json')) {
            res.setHeader('Content-Type', 'application/json; charset=utf-8')
            res.setHeader('Access-Control-Allow-Origin', '*')
            res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate')
            res.end(fs.readFileSync(filePath))
          } else if (/\.(jpg|jpeg|png|gif|webp)$/i.test(filePath)) {
            const ext = filePath.split('.').pop()!.toLowerCase()
            const mime = ext === 'jpg' || ext === 'jpeg' ? 'image/jpeg'
              : ext === 'png' ? 'image/png'
              : ext === 'webp' ? 'image/webp'
              : 'image/gif'
            res.setHeader('Content-Type', mime)
            res.setHeader('Cache-Control', 'public, max-age=86400')
            res.end(fs.readFileSync(filePath))
          } else {
            next()
          }
        })
      },
    },
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
