import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import proxyOptions from './proxyOptions.js';

// Single-page CRM build. Source lives under frontend/src (+ frontend/shared for
// the Frappe API client). Output goes to upande_crm/public/frontend/, served by
// Frappe at /assets/upande_crm/frontend/ (matching `base`). scripts/build-html.mjs
// then writes the emitted index.html to upande_crm/www/customer-relationship-management.html with the Jinja
// boot block so the SPA mounts at /customer-relationship-management.
export default defineConfig({
  plugins: [react()],
  base: '/assets/upande_crm/frontend/',
  resolve: {
    alias: {
      '@shared': path.resolve(__dirname, 'shared'),
      // shadcn convention
      '@': path.resolve(__dirname, 'src'),
    },
  },
  build: {
    outDir: path.resolve(__dirname, '../upande_crm/public/frontend'),
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      input: { crm: path.resolve(__dirname, 'index.html') },
      output: {
        entryFileNames: 'assets/[name]-[hash].js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash].[ext]',
      },
    },
  },
  server: {
    port: 8085,
    fs: { allow: [__dirname] },
    proxy: proxyOptions('/assets/upande_crm/frontend/'),
  },
});
