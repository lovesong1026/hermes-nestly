import path from 'node:path'
import { fileURLToPath } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// SPA for the web_chat gateway platform.
//
// Build target: ``../gateway/web/_static/`` — the WebChatAdapter serves
// this directory under ``/static/*`` and the SPA shell under ``/``.
//
// Dev server: ``:5173`` with ``/api/*`` proxied to the gateway's
// web_chat port (``:8643``) and Platform API (``:8700``).

const projectRoot = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(projectRoot, './src'),
    },
  },
  build: {
    outDir: path.resolve(projectRoot, '../gateway/web/_static'),
    emptyOutDir: true,
    sourcemap: true,
    // Usage Center (+ Chart.js) is lazy-loaded from App so the chat shell
    // stays smaller; other routes remain in the main chunk for now.
  },
  server: {
    host: true, // 0.0.0.0 — LAN devices can open http://<lan-ip>:5173
    port: 5173,
    proxy: {
      '/api/v1': {
        target: 'http://127.0.0.1:8700',
        changeOrigin: false,
      },
      '/api': {
        target: 'http://127.0.0.1:8643',
        changeOrigin: false,
      },
    },
  },
})
