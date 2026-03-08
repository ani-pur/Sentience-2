import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:3000',
        changeOrigin: true,
      },
      '/login': {
        target: 'http://localhost:3000',
        changeOrigin: true,
      },
      '/signup': {
        target: 'http://localhost:3000',
        changeOrigin: true,
      },
      '/logout': {
        target: 'http://localhost:3000',
        changeOrigin: true,
      },
    },
  },
})
