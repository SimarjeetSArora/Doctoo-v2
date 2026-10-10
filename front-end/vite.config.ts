import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    // "@/..." points to src/, e.g. import { api } from '@/lib/api'
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    // During development, forward /api requests to the FastAPI server.
    proxy: { '/api': 'http://localhost:8000' },
  },
})
