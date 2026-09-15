import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In dev, proxy /search and /healthz to the FastAPI server on :8000
// so we don't hit CORS issues and the frontend URL stays clean.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/search': 'http://localhost:8000',
      '/healthz': 'http://localhost:8000',
      '/metrics': 'http://localhost:8000',
    },
  },
})
