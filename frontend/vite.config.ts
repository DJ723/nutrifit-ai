import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    // 监听 0.0.0.0，让同一局域网内的手机可以访问
    host: true,
    port: 5175,
    proxy: {
      // 手机访问 /api 时由本机 Vite 转发到后端，因此后端不必对外暴露
      '/api': 'http://127.0.0.1:8008',
      '/storage': 'http://127.0.0.1:8008'
    }
  }
})
