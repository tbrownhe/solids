export const SITE = 'https://solids.tobiasbrownheft.xyz'
export const GUIDE = '/guide/slab-polyhedra/'
const creator = { '@type': 'Person', '@id': `${SITE}/#creator`, name: 'Tobias Brown-Heft', url: 'https://tobiasbrownheft.xyz/' }
export const homeMeta = {
  title: 'Solids — Printable Polyhedron Templates for Ceramic Slab Building',
  description: 'Design geometric ceramic sculptures with printable polyhedron templates, bevel settings, and custom dimensions for slab clay. Explore convex and recessed forms.',
  path: '/', socialTitle: 'Solids — Geometry, Made Tangible',
  socialDescription: 'Turn mathematical solids into ceramic sculpture. Create scaled slab templates with edge-by-edge bevel angles.',
  schema: { '@context': 'https://schema.org', '@type': 'WebApplication', '@id': `${SITE}/#app`, name: 'Solids', url: `${SITE}/`, description: 'A free ceramic slab template designer with printable polygon panels, bevel settings, shrinkage compensation and experimental recessed constructions.', applicationCategory: 'DesignApplication', operatingSystem: 'Any', browserRequirements: 'JavaScript enabled for the designer; WebGL for the 3D preview.', isAccessibleForFree: true, offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' }, creator, image: `${SITE}/og/solids-social.png` },
}
export const guideMeta = {
  title: 'Building Polyhedra from Slab Clay: Templates & Bevel Angles — Solids',
  description: 'Learn to build polyhedra from clay slabs: size panels, allow for shrinkage, set convex and reflex bevels, check print scale, and test joins before assembly.',
  path: GUIDE, socialTitle: 'From Geometry to Clay — The Solids Cutting Guide',
  socialDescription: 'A practical guide to slab thickness, shrinkage, printable panel templates and bevel settings measured from the clay surface.',
  schema: { '@context': 'https://schema.org', '@type': 'Article', headline: 'Building polyhedra from slab clay', description: 'A practical methodology for ceramic polygon panels, symmetric bevel settings and printing at actual size.', url: `${SITE}${GUIDE}`, mainEntityOfPage: `${SITE}${GUIDE}`, author: creator, image: `${SITE}/og/solids-social.png`, inLanguage: 'en' },
}
export function renderHead(meta: typeof homeMeta | typeof guideMeta) {
  const escape = (s: string) => s.replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;')
  const tag = (key: string, value: string, property = false) => `<meta ${property ? 'property' : 'name'}="${key}" content="${escape(value)}" />`
  return [
    `<title>${escape(meta.title)}</title>`, tag('description', meta.description), tag('author', 'Tobias Brown-Heft'),
    `<link rel="canonical" href="${SITE}${meta.path}" />`,
    '<link rel="icon" type="image/svg+xml" href="/icon.svg" />',
    '<link rel="icon" type="image/png" sizes="32x32" href="/icon-32.png" />',
    '<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png" />',
    ...Object.entries({ 'og:type': 'website', 'og:title': meta.socialTitle, 'og:description': meta.socialDescription, 'og:url': `${SITE}${meta.path}`, 'og:site_name': 'Solids', 'og:image': `${SITE}/og/solids-social.png`, 'og:image:type': 'image/png', 'og:image:width': '1200', 'og:image:height': '630', 'og:image:alt': 'An illustrated faceted clay-colored polyhedron beside a polygon template. Solids: Geometry, made tangible.' }).map(([k,v]) => tag(k,v,true)),
    ...Object.entries({ 'twitter:card': 'summary_large_image', 'twitter:title': meta.socialTitle, 'twitter:description': meta.socialDescription, 'twitter:image': `${SITE}/og/solids-social.png`, 'twitter:image:alt': 'An illustrated clay-colored polyhedron and a polygon panel template.' }).map(([k,v]) => tag(k,v)),
    `<script type="application/ld+json">${JSON.stringify(meta.schema).replaceAll('<','\\u003c')}</script>`,
  ].join('\n    ')
}
