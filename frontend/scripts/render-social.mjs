import {chromium} from '@playwright/test'
import {readFile} from 'node:fs/promises'
const browser=await chromium.launch({headless:true,args:['--no-sandbox']})
try {
  const page=await browser.newPage({viewport:{width:1200,height:630},deviceScaleFactor:1})
  await page.setContent(`<style>html,body{margin:0}svg{display:block}</style>${await readFile('public/og/solids-social.svg','utf8')}`)
  await page.evaluate(()=>document.fonts.ready)
  await page.locator('svg').screenshot({path:'public/og/solids-social.png'})
  const icon=await readFile('public/icon.svg','utf8')
  for(const [size,path] of [[32,'public/icon-32.png'],[180,'public/apple-touch-icon.png']]) {
    await page.setViewportSize({width:size,height:size})
    await page.setContent(`<style>html,body{margin:0}svg{display:block;width:${size}px;height:${size}px}</style>${icon}`)
    await page.locator('svg').screenshot({path})
  }
  console.log('Rendered social card (1200 × 630) and PNG icons from original SVG assets.')
} finally {await browser.close()}
