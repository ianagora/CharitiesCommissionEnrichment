import { defineConfig } from 'vite'
import pages from '@hono/vite-cloudflare-pages'

export default defineConfig({
  plugins: [pages()],
  build: {
    outDir: 'dist',
    minify: 'esbuild',
    sourcemap: false,
  },
  server: {
    port: 3000,
    host: '0.0.0.0',
  },
})
