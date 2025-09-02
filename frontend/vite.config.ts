import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: ['closet.local']
  },
  build: {
    // Simple build configuration without complex chunking
    chunkSizeWarningLimit: 1000,
    sourcemap: true
  }
})
