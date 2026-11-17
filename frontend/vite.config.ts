// Vite serves the app on :5173 and forwards /api/* (and slide images under /media/*) to the FastAPI backend on :8000.
import { defineConfig } from 'vitest/config';

export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      // PowerPoint slides reference their images at /media/{deck}/{name}, served as-is by the backend.
      '/media': 'http://127.0.0.1:8000',
    },
  },
  build: {
    rollupOptions: {
      // lucide-react marks its modules "use client" (for React Server Components); harmless here.
      onwarn(warning, warn) {
        if (warning.code !== 'MODULE_LEVEL_DIRECTIVE') warn(warning);
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['src/test/setup.ts'],
  },
});
