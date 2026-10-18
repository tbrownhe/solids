import {readFile, readdir, writeFile, mkdir, rm} from 'node:fs/promises'
import {resolve} from 'node:path'
import {pathToFileURL} from 'node:url'
import {build} from 'vite'

// Node renders content only during the build. FastAPI serves plain HTML at runtime.
const temporary='node_modules/.solids-prerender'
await build({publicDir:false,build:{ssr:'src/prerender.tsx',outDir:temporary,emptyOutDir:true,rollupOptions:{output:{entryFileNames:'prerender.mjs'}}}})
try {
  const {renderHome,renderGuide,renderHead,guideMeta,GUIDE,SITE}=await import(pathToFileURL(resolve(temporary,'prerender.mjs')).href)
  const fonts=(await readdir('dist/assets')).filter(name=>/^(dm-serif-display-latin-400-normal|dm-sans-latin-wght-normal)-.*\.woff2$/.test(name))
  const preloads=fonts.map(name=>`<link rel="preload" href="/assets/${name}" as="font" type="font/woff2" crossorigin />`).join('\n    ')
  const template=(await readFile('dist/index.html','utf8')).replace('</head>',`    ${preloads}\n  </head>`)
  if (!template.includes('<!--app-html-->')) throw new Error('Missing prerender outlet')
  await writeFile('dist/index.html',template.replace('<!--app-html-->',renderHome()))
  // The evergreen guide is fully static and needs no application JavaScript.
  const guide=template.replace(/<!--seo:start-->[\s\S]*?<!--seo:end-->/,renderHead(guideMeta))
    .replace(/\s*<script type="module"[^>]*><\/script>/g,'')
    .replace(/\s*<link rel="modulepreload"[^>]*>/g,'')
    .replace('<!--app-html-->',renderGuide())
  if (!guide.includes(`href="${SITE}${GUIDE}"`)) throw new Error('Guide canonical was not generated')
  await mkdir(`dist${GUIDE}`,{recursive:true})
  await writeFile(`dist${GUIDE}index.html`,guide)
  await writeFile('dist/robots.txt',`User-agent: *\nAllow: /\nDisallow: /api/\n\nSitemap: ${SITE}/sitemap.xml\n`)
  await writeFile('dist/sitemap.xml',`<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${['/',GUIDE].map(path=>`  <url><loc>${SITE}${path}</loc></url>`).join('\n')}\n</urlset>\n`)
  console.log('Prerendered homepage, static guide, robots and two-page sitemap.')
} finally {await rm(temporary,{recursive:true,force:true})}
