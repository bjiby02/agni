import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Cursor's browser pane often cannot reach :8000 directly.
// Proxy /api (and health) through the Vite origin so the console works.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/sos': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});
