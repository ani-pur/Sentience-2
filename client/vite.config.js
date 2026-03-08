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
        headers: { 'x-vite-proxy': '1' },
      },
      '/login': {
        target: 'http://localhost:3000',
        changeOrigin: true,
        headers: { 'x-vite-proxy': '1' },
      },
      '/signup': {
        target: 'http://localhost:3000',
        changeOrigin: true,
        headers: { 'x-vite-proxy': '1' },
      },
      '/logout': {
        target: 'http://localhost:3000',
        changeOrigin: true,
        headers: { 'x-vite-proxy': '1' },
      },
      '/landing': {
        target: 'http://localhost:3000',
        changeOrigin: true,
        headers: { 'x-vite-proxy': '1' },
      },
    },
  },
})
