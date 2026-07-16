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
        // Only React core (react, react-dom, scheduler) gets its own chunk. It is
        // a dependency LEAF — it imports nothing else — so every other chunk can
        // depend on it one-directionally and no chunk cycle is possible.
        //
        // Do NOT split further (e.g. a separate `charts` chunk, or matching a bare
        // /react/): recharts/d3 and the radix/lucide/zustand libraries share small
        // transitive deps (clsx, react-is, es-toolkit…). Any split that scatters
        // those shared modules makes two chunks import each other, and a circular
        // chunk dependency crashes at module-eval time before React mounts — the
        // page goes blank. Symptoms seen from this exact footgun:
        //   • react ↔ vendor  → "Cannot read properties of undefined (reading 'useState')"
        //   • charts ↔ vendor → "Cannot access 'Pu' before initialization"
        // The charts code isn't lazy-loaded (Overview renders it on first paint),
        // so a separate charts chunk bought nothing anyway. One `vendor` chunk for
        // everything-but-React keeps the graph acyclic and correct.
        manualChunks(id) {
          if (!id.includes('node_modules')) return;
          if (/[\\/]node_modules[\\/](react|react-dom|scheduler)[\\/]/.test(id)) return 'react';
          return 'vendor';
        },
      },
    },
  },
  server: {
    port: 8085,
    fs: { allow: [__dirname] },
    proxy: proxyOptions('/assets/upande_crm/frontend/'),
  },
});
