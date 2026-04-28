import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/upload': 'http://localhost:8000',
      '/stream': 'http://localhost:8000',
      '/alerts': 'http://localhost:8000',
      '/logs': 'http://localhost:8000',
      '/report': 'http://localhost:8000',
      '/analytics': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/jobs': 'http://localhost:8000',
    },
  },
});
