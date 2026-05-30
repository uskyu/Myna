import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: '../src/web/public',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: 'assets/[name]-[hash].js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash].[ext]'
      }
    }
  },
  server: {
    proxy: {
      '/admin': 'http://localhost:3456',
      '/bot': 'http://localhost:3456',
      '/uploads': 'http://localhost:3456',
      '/health': 'http://localhost:3456',
      '/ws': { target: 'ws://localhost:3456', ws: true }
    }
  }
})
