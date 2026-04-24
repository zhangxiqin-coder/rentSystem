import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  // 生产环境优化
  build: {
    // 启用代码分割，减少单个文件大小
    rollupOptions: {
      output: {
        manualChunks(id) {
          // 将 Element Plus 单独分割
          if (id.includes('node_modules/element-plus') || id.includes('node_modules/@element-plus')) {
            return 'element-plus'
          }
          // 将 Vue 生态单独分割
          if (id.includes('node_modules/vue') || id.includes('node_modules/@vue') || id.includes('node_modules/pinia') || id.includes('node_modules/vue-router')) {
            return 'vue-vendor'
          }
        },
      },
    },
    // 启用 CSS 代码分割
    cssCodeSplit: true,
    // 压缩配置
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true,
      },
    },
    // 设置 chunk 大小警告阈值
    chunkSizeWarningLimit: 1000,
    // 启用 source map（生产环境可以关闭以减小体积）
    sourcemap: false,
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    // 禁用 HMR（如果不需要热更新）
    hmr: true,
    // 关闭 WebSocket，使用普通 HTTP 轮询
    watch: {
      usePolling: false,
    },
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  // 优化预构建
  optimizeDeps: {
    include: ['vue', 'vue-router', 'pinia', 'element-plus', 'axios'],
  },
  // 生产环境不生成 manifest.json（如果不需要）
  manifest: false,
})
