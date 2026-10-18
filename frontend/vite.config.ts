import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { homeMeta, renderHead } from './src/seo'

export default defineConfig({
  plugins: [react(), { name: 'solids-metadata', transformIndexHtml: html => html.replace('<!--seo-head-->', `<!--seo:start-->${renderHead(homeMeta)}<!--seo:end-->`) }],
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } },
})
