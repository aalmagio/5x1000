import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api.php': 'http://localhost:8080',
    },
  },
  build: {
    // Output nella cartella public/ (document root nginx)
    // emptyOutDir: false per non cancellare api.php e .env
    outDir: '../public',
    emptyOutDir: false,
    assetsDir: 'assets',
  },
})
