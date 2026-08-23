import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  // Default 8002 — orphan pre-SP-042c uvicorn often blocks :8001 (Access denied to kill).
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = env.VITE_API_PROXY_TARGET || 'http://localhost:8002'

  return {
    plugins: [react()],
    server: {
      // Default 5175 — avoids collision with the Weathero project on :5173.
      port: Number(env.VITE_DEV_PORT) || 5175,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
        },
        '/health': {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
