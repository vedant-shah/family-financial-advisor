import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Backend location: 'http://localhost:8000' for plain local dev, or the backend
// service URL inside Docker (set via VITE_PROXY_TARGET in docker-compose.yml).
const proxyTarget = process.env.VITE_PROXY_TARGET || 'http://localhost:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // host: true binds 0.0.0.0 so the dev server is reachable from outside a container.
    host: true,
    // Allow any *.local Bonjour/mDNS hostname so family devices on the home LAN
    // can reach the dev server at e.g. http://Vedants-MacBook-Air.local:5173
    allowedHosts: ['.local'],
    // Bind-mount file events are unreliable on Docker Desktop; poll when asked to.
    watch: process.env.VITE_USE_POLLING ? { usePolling: true } : undefined,
    // '/api/*' proxied with path kept intact (backend serves /api/members etc.)
    // '/chat' and '/session' pass through as-is (Day 1 backend paths, no rewrite)
    proxy: {
      '/api': { target: proxyTarget, changeOrigin: true },
      '/chat': { target: proxyTarget, changeOrigin: true },
      '/session': { target: proxyTarget, changeOrigin: true },
    },
  },
})
