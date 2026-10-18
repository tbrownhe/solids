import {StrictMode,useEffect,useRef,useState} from 'react'
import {createRoot,hydrateRoot} from 'react-dom/client'
import {ArrowRight,MoveUpRight,X} from 'lucide-react'
import {Designer} from './Designer'
import {BevelerNote} from './BevelerNote'
import {HomeIntro,MethodSections} from './Editorial'
import {GUIDE} from './seo'
import type {Design} from './types'
import './style.css'
import './editorial.css'
import './workspace.css'

export function App() {
  const [design,setDesign]=useState<Design|null>(null)
  const [helpOpen,setHelpOpen]=useState(false)
  const help=useRef<HTMLDialogElement>(null)
  useEffect(()=>{if(helpOpen)help.current?.showModal();else help.current?.close()},[helpOpen])
  return <>
    <a className="skip-link" href="#studio">Skip to the designer</a>
    <header className="masthead">
      <a href="/" className="wordmark" aria-label="Solids home"><svg viewBox="0 0 32 34" aria-hidden="true"><path d="M16 2 30 10 30 25 16 33 2 25 2 10Z M2 10 16 18 30 10 M16 18V33 M16 2V18 M2 25 16 18 30 25"/></svg>solids<span className="wordmark-dot">.</span></a>
      <nav className="site-nav" aria-label="Main navigation"><a href="#studio">Design</a><a href="#method">Method</a><a href="#faq">FAQ</a></nav>
      <button className="text-button" onClick={()=>setHelpOpen(true)}>The cutting guide <MoveUpRight size={14}/></button>
    </header>
    <main><HomeIntro/><noscript><p className="script-note">The interactive designer needs JavaScript. You can read the <a href={GUIDE}>complete slab-building guide</a> without it.</p></noscript><Designer onDesign={setDesign} onOpenHelp={()=>setHelpOpen(true)}/><MethodSections/><footer><span>solids. <span className="muted">A little geometry for your clay practice.</span></span><a href={GUIDE}>Slab-building guide</a><span>Measure twice. Make slowly.</span></footer></main>
    <dialog ref={help} onCancel={() => setHelpOpen(false)} onClick={e => { if (e.target === help.current) setHelpOpen(false) }} aria-labelledby="guide-title"><div className="dialog-top"><span className="eyebrow">AT THE WORKBENCH</span><button className="icon-button" aria-label="Close cutting guide" onClick={() => setHelpOpen(false)}><X size={20}/></button></div><h2 id="guide-title">{design?.phase2 ? <>IN or OUT?<br/><em>Keep the reference.</em></> : <>Interior face up.<br/><em>Exterior face down.</em></>}</h2>
      {design?.phase2 && <div className="phase2-guide"><p><strong>IN = interior face up. OUT = exterior face up.</strong> Mixed panels need cuts from both sides. Both settings are angles from the slab plane, with 90° normal to it.</p><p>Trace the solid <strong>extended blank</strong>, with the interior up. Keep the template ID and transfer edge IDs before turning the clay over. For OUT edges, remove upper exterior waste back to the <strong>dash-dot exterior reference</strong>. The dashed polygon is the final interior surface.</p><svg viewBox="0 0 420 135" className="section-diagram" role="img" aria-label="Exterior-up cut for reflex joint: upper exterior waste is removed from the extended blank, with the enlarged interior face underneath."><path d="M100 35H350V95H65Z" fill="#ddd7c7" stroke="#535d4b"/><path d="M65 35H100L65 95Z" fill="#d99b78" stroke="#a75d3b" strokeDasharray="4 4"/><text x="120" y="20">OUT: EXTERIOR FACE UP</text><text x="110" y="117">INTERIOR DOWN / extended edge</text><text x="0" y="52">upper waste</text></svg><p><strong>Calibration first:</strong> at 6 mm working thickness, a convex 120° joint and a reflex 240° joint both use a 60° tool setting. The former insets the interior edge 3.4641 mm; the latter needs a 3.4641 mm outward extension. Dry-fit both in scrap before committing a full set.</p><p>Solid outline = blank. Dash-dot = exterior reference. Dashed = interior surface. Dimensions on the PDF refer to the reference edges, not the expanded blank. Thick-panel overlaps are marked on the templates for manual relief; the PDF includes an instance reference.</p></div>}
      <svg className="section-diagram" viewBox="0 0 460 190" role="img" aria-label="Cutting and beveling position: interior face up, exterior face down. Remove the upper waste wedge and preserve the lower exterior edge."><path d="M115 65 350 65 350 135 80 135Z" fill="#ddd7c7" stroke="#535d4b" strokeWidth="1.5"/><path d="M80 65H115L80 135Z" fill="#d99b78" fillOpacity=".25" stroke="#a75d3b" strokeDasharray="4 4"/><path d="M80 135 115 65" stroke="#a75d3b" strokeWidth="3"/><path d="M35 135H395" stroke="#89917c" strokeDasharray="3 5"/><text x="180" y="45">INTERIOR / face up</text><text x="95" y="165">EXTERIOR / face down — preserve this edge</text><path d="M98 135A18 18 0 0 0 88 119" fill="none" stroke="#a75d3b"/><text x="105" y="126">θ</text><text x="5" y="82" fill="#a75d3b">upper waste</text><path d="M62 87 88 83" stroke="#a75d3b"/><text x="270" y="105">working slab</text></svg>
      <BevelerNote detailed/>
      {!design?.phase2 && <ol><li><strong>Roll your clay.</strong> Use its working thickness and total linear shrinkage from cutting to fired.</li><li><strong>Print at 100% / Actual Size.</strong> Disable Fit to Page. Measure the PDF’s 100 mm ruler and 1-inch square.</li><li><strong>Cut with the exterior face down.</strong> Keep the interior face up and trace the full solid outline onto it. This is the full exterior footprint before beveling. Cut the shape and make the labeled quantity.</li><li><strong>Bevel in that same position.</strong> Keep the exterior face down and the interior face up throughout cutting and beveling. Remove the upper waste at each labeled tool angle, preserving the exterior edge underneath. The dashed polygon shows the remaining upper interior face.</li><li><strong>Test a scrap joint.</strong> Tool settings describe ideal geometry; clay moisture, scoring, slip, and wire movement affect the fit.</li></ol>}
      <p className="guide-footnote">For tiled panels, align matching registration crosses in the 10 mm overlap. Join the complete outline before tracing. Never mirror a chiral template.</p>
      <button className="download-button" onClick={() => setHelpOpen(false)}>Back to the studio <ArrowRight size={16}/></button>
    </dialog>
  </>
}
if(typeof document!=='undefined') {
  const root=document.getElementById('root')!
  const app=<StrictMode><App/></StrictMode>
  if(root.hasChildNodes())hydrateRoot(root,app)
  else createRoot(root).render(app)
}
