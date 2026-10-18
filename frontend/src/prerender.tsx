import { renderToString } from 'react-dom/server'
import { App } from './main'
import { GuidePage } from './Editorial'
export { GUIDE, SITE, guideMeta, renderHead } from './seo'
export const renderHome = () => renderToString(<App/>)
export const renderGuide = () => renderToString(<GuidePage/>)
