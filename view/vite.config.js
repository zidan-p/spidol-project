import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Dev mode (`python main.py --dev`) runs the WebSocket server on :8765
    // and (eventually) a REST/static surface on :5000 independently of the
    // Vite dev server on :5173. No proxy rule is required for the WebSocket
    // connection itself (the frontend connects directly to ws://127.0.0.1:8765
    // per SPEC.md section 4), but routes under /api are proxied to the
    // production-mode static/API host for parity with the built bundle.
    proxy: {
      '/api': 'http://127.0.0.1:5000',
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
  },
})
