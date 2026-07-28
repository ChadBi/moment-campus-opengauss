import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(rootDir, './src'),
    },
  },
  server: {
    // 代理 API 请求到后端，避免浏览器跨域问题（MCP 浏览器测试时尤为重要）
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/uploads': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    // P2-001: 拆分大依赖到独立 chunk，避免单个 chunk 超 500KB 警告
    // MapPage 由 1043KB 降至约 30KB（仅业务代码），maplibre-gl 单独成 chunk
    rollupOptions: {
      output: {
        // Rolldown 要求 manualChunks 为函数形式
        manualChunks: (id: string) => {
          if (id.includes('node_modules')) {
            if (id.includes('maplibre-gl')) return 'maplibre-gl';
            if (id.includes('react-router')) return 'react-vendor';
            if (id.includes('react-dom')) return 'react-vendor';
            if (id.includes(path.join('react', path.sep)) && !id.includes('react-router')) {
              // 精确匹配 react 核心，避免误匹配 react-* 第三方包
              return 'react-vendor';
            }
            if (id.includes('lucide-react')) return 'icons';
          }
          return undefined;
        },
      },
    },
    chunkSizeWarningLimit: 600,
  },
})
