import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Relative base path for native desktop webview embedding
export default defineConfig({
  plugins: [react()],
  base: './',
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false
  }
});
