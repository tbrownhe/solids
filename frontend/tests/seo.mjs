import assert from 'node:assert/strict'
import {mkdir,writeFile} from 'node:fs/promises'
import {chromium,expect} from '@playwright/test'

const baseURL=process.env.STUDIO_URL ?? 'http://127.0.0.1:8081'
const canonical='https://solids.tobiasbrownheft.xyz'
const guide='/guide/slab-polyhedra/'
const artifacts=new URL('../../artifacts/seo/',import.meta.url).pathname
await mkdir(artifacts,{recursive:true})
const browser=await chromium.launch({headless:true,args:['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader']})
try {
  // Social crawlers and non-JavaScript readers must get useful initial HTML.
  const offline=await browser.newContext({baseURL,javaScriptEnabled:false,viewport:{width:390,height:844}})
  const page=await offline.newPage()
  for(const path of ['/',guide]) {
    const response=await page.goto(path)
    assert.equal(response.status(),200)
    assert(!response.headers()['x-robots-tag']?.includes('noindex'))
    const html=await response.text()
    assert.equal(response.headers()['cache-control'],'no-cache')
    assert.equal((html.match(/<h1\b/g) ?? []).length,1)
    assert(!html.includes('<!--app-html-->'))
    assert(!/<meta[^>]+(?:name|content)="[^"]*noindex/i.test(html))
    for(const selector of ['title','meta[name=description]','link[rel=canonical]','meta[property="og:title"]','meta[property="og:description"]','meta[property="og:url"]','meta[property="og:image"]','meta[name="twitter:card"]','meta[name="twitter:title"]','meta[name="twitter:description"]','meta[name="twitter:image"]','script[type="application/ld+json"]']) {
      assert.equal(await page.locator(selector).count(),1,`${path}: ${selector}`)
    }
    await expect(page.locator('link[rel=canonical]')).toHaveAttribute('href',canonical+path)
    const stylesheet=await page.locator('link[rel=stylesheet]').first().getAttribute('href')
    assert.match((await page.request.get(stylesheet)).headers()['cache-control'],/max-age=31536000, immutable/)
    const description=await page.locator('meta[name=description]').getAttribute('content')
    assert(description.length>=150 && description.length<=160)
    await expect(page.locator('meta[property="og:image"]')).toHaveAttribute('content',canonical+'/og/solids-social.png')
    await expect(page.locator('meta[name="twitter:card"]')).toHaveAttribute('content','summary_large_image')
    const schema=JSON.parse(await page.locator('script[type="application/ld+json"]').textContent())
    assert.equal(schema['@context'],'https://schema.org')
    assert.equal(schema.url,canonical+path)
    assert.equal((schema.creator ?? schema.author).name,'Tobias Brown-Heft')
    assert(!schema.aggregateRating && !schema.review)
    if(path==='/') {
      assert.equal(schema['@type'],'WebApplication')
      assert.equal(schema.offers.price,'0')
      assert.equal(schema.isAccessibleForFree,true)
      await expect(page.getByRole('heading',{level:1})).toHaveText('Geometry, made tangible.')
      await expect(page.getByText('I built Solids',{exact:false})).toBeVisible()
      await expect(page.getByRole('heading',{name:'What are bevel angles?'})).toBeVisible()
      await expect(page.locator('noscript')).toBeVisible()
    } else {
      assert.equal(schema['@type'],'Article')
      // The guide has no app JavaScript. Cloudflare may append its existing
      // analytics beacon at the edge, independently of the static origin page.
      const modules=await page.locator('script[type=module]').evaluateAll(nodes=>nodes.map(node=>node.getAttribute('src')))
      assert(modules.every(src=>src && new URL(src,baseURL).hostname==='static.cloudflareinsights.com'))
      await expect(page.getByRole('heading',{name:'Keep the reference edge, and follow the cut side'})).toBeVisible()
      await expect(page.locator('#cutting')).toContainText('exterior face down throughout cutting and beveling')
      await expect(page.locator('#cutting')).toContainText('A panel with IN and OUT edges needs bevels from both sides')
    }
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true)
    await page.screenshot({path:`${artifacts}no-js-${path==='/'?'home':'guide'}-mobile.png`,fullPage:true})
    await writeFile(`${artifacts}metadata-${path==='/'?'home':'guide'}.html`,html.slice(html.indexOf('<head>'),html.indexOf('</head>')+7))
    for(const href of await page.locator('a[href^="#"]').evaluateAll(nodes=>nodes.map(node=>node.getAttribute('href')))) {
      assert.equal(await page.locator(`[id="${href.slice(1)}"]`).count(),1,`Broken anchor ${href}`)
    }
  }
  const redirect=await page.request.get('/guide/slab-polyhedra',{maxRedirects:0})
  assert.equal(redirect.status(),308)
  assert(redirect.headers().location.endsWith(guide))
  assert.equal((await page.request.get('/missing-seo-page')).status(),404)
  const robots=await page.request.get('/robots.txt')
  assert.equal(robots.status(),200)
  assert.match(await robots.text(),new RegExp(`Sitemap: ${canonical}/sitemap.xml`))
  const sitemap=await page.request.get('/sitemap.xml')
  assert.equal(sitemap.status(),200)
  assert.match(sitemap.headers()['content-type'],/xml/)
  const urls=[...(await sitemap.text()).matchAll(/<loc>(.*?)<\/loc>/g)].map(match=>match[1])
  assert.deepEqual(urls,[canonical+'/',canonical+guide])
  for(const [path,width,height] of [['/og/solids-social.png',1200,630],['/icon-32.png',32,32],['/apple-touch-icon.png',180,180]]) {
    const image=await page.request.get(path)
    assert.equal(image.status(),200)
    assert.match(image.headers()['content-type'],/^image\/png/)
    const bytes=await image.body()
    assert.equal(bytes.readUInt32BE(16),width)
    assert.equal(bytes.readUInt32BE(20),height)
    assert(bytes.length<350000)
  }
  await offline.close()
  const context=await browser.newContext({baseURL,viewport:{width:1440,height:1050}})
  const interactive=await context.newPage()
  const errors=[]
  interactive.on('pageerror',error=>errors.push(error.message))
  interactive.on('console',message=>{if(message.type()==='error') errors.push(message.text())})
  await interactive.goto('/')
  await expect(interactive.getByRole('button',{name:'Download PDF',exact:true})).toBeEnabled()
  await expect(interactive.locator('.solid-canvas canvas')).toBeVisible()
  await interactive.getByRole('link',{name:'Start designing',exact:true}).click()
  await expect(interactive.locator('#studio')).toBeFocused()
  await interactive.locator('#shrinkage').fill('10')
  await expect(interactive.locator('.working-edge strong')).toContainText('133.33')
  await interactive.reload()
  await expect(interactive.locator('#shrinkage')).toHaveValue('10')
  await expect(interactive.getByRole('button',{name:'Download PDF',exact:true})).toBeEnabled()
  // A direct guide visit retains correct static metadata and avoids the 3D bundle.
  const requests=[]
  interactive.on('request',request=>requests.push(request.url()))
  await interactive.goto(guide)
  assert(!requests.some(url=>url.includes('SolidView-')))
  await interactive.screenshot({path:`${artifacts}guide-desktop.png`,fullPage:true})
  assert.deepEqual(errors,[],'No hydration or browser errors')
  await context.close()
  console.log('SEO QA passed: raw HTML, no-JS home/guide, unique headings/metadata, canonical URLs, JSON-LD, social PNGs/icons, robots, sitemap, redirects/404s, anchors/focus, mobile overflow, saved preferences and hydration.')
} finally {await browser.close()}
