import { StrictMode, useEffect, useRef, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { ArrowDownToLine, ArrowRight, Box, Check, ChevronDown, Download, Expand, Layers3, LoaderCircle, MoveUpRight, RotateCcw, Ruler, X } from 'lucide-react'
import { SolidView } from './SolidView'
import { Panel } from './Panel'
import type { Design, Parameters, Solid, Preset, FaceTransform } from './types'
import { COLORS } from './types'
import './style.css'

const defaults: Parameters = { solid_id: 'rhombicuboctahedron', edge_length_mm: 120, thickness_mm: 6, shrinkage_percent: 0, page_format: 'letter', angle_precision: 2, preset_id:null, apex_offset_mm:20, face_transforms:{} }
const polygonName: Record<number, string> = { 3: 'Triangle', 4: 'Square', 5: 'Pentagon', 6: 'Hexagon', 8: 'Octagon', 10: 'Decagon' }
function BevelerNote({ detailed = false }: { detailed?: boolean }) {
  return <p className="tool-note">Optimized for adjustable wire bevelers such as the <a href="https://www.etsy.com/listing/4466016418/precision-beveler-pottery-bevel-cutter" target="_blank" rel="noreferrer">{detailed ? 'Precision Beveler – Pottery Bevel Cutter – Custom Angle Beveler' : 'Precision Beveler'}</a> by KellyHoferStudios.</p>
}
function readParameters(): Parameters {
  try {
    const stored = localStorage.getItem('solids.parameters')
    const parsed=stored ? JSON.parse(stored) : null
    return parsed ? { ...defaults, ...(parsed.parameters ?? parsed) } : defaults
  } catch { return defaults }
}
async function responseError(response: Response) {
  const data = await response.json().catch(() => ({}))
  if (typeof data.detail === 'string') return data.detail
  if (Array.isArray(data.detail)) {
    const fields: Record<string, string> = { edge_length_mm: 'Finished edge length', thickness_mm: 'Slab thickness', shrinkage_percent: 'Shrinkage', angle_precision: 'Angle decimals', solid_id: 'Solid', page_format: 'Paper size' }
    return data.detail.map((d: { loc: string[]; msg: string }) => `${fields[d.loc.at(-1) ?? ''] ?? 'Setting'}: ${d.msg}`).join('; ')
  }
  return `Could not complete the request (${response.status}).`
}

function App() {
  const [parameters, setParameters] = useState<Parameters>(readParameters)
  const [catalog, setCatalog] = useState<Solid[]>([])
  const [presets,setPresets]=useState<Preset[]>([])
  const [selectedFaceId,setSelectedFaceId]=useState<string|null>(null)
  const [exteriorView,setExteriorView]=useState(false)
  const [design, setDesign] = useState<Design | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState('')
  const [view, setView] = useState<'solid' | 'panels'>('solid')
  const [selected, setSelected] = useState<string | null>(null)
  const [selectedEdge, setSelectedEdge] = useState<number | null>(null)
  const [resetKey, setResetKey] = useState(0)
  const [helpOpen, setHelpOpen] = useState(false)
  const help = useRef<HTMLDialogElement>(null)
  const faceEditor=useRef<HTMLDetailsElement>(null)
  const loadInput=useRef<HTMLInputElement>(null)
  useEffect(() => {
    const controller = new AbortController()
    fetch('/api/solids', { signal: controller.signal }).then(async r => {
      if (!r.ok) throw new Error(await responseError(r))
      setCatalog(await r.json())
    }).catch(e => { if (e.name !== 'AbortError') setError('The studio could not connect. Check that the local API is running.') })
    fetch('/api/presets',{signal:controller.signal}).then(async r => {
      if (!r.ok) throw new Error(await responseError(r))
      setPresets(await r.json())
    }).catch(e => { if (e.name!=='AbortError') setExportError('Construction presets could not be loaded.') })
    return () => controller.abort()
  }, [])
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError('')
    setExportError('')
    const timer = setTimeout(async () => {
      try {
        if (Object.values(parameters).some(v => typeof v === 'number' && !Number.isFinite(v))) throw new Error('Enter a number in each dimension field.')
        const r = await fetch('/api/design', { method: 'POST', body: JSON.stringify(parameters), headers: { 'Content-Type': 'application/json' }, signal: controller.signal })
        if (!r.ok) throw new Error(await responseError(r))
        const result: Design = await r.json()
        setDesign(result)
        setSelected(null)
        setSelectedEdge(null)
        localStorage.setItem('solids.parameters', JSON.stringify({format:'solids-studio',version:2,geometry_version:2,parameters}))
      } catch (e) {
        if (e instanceof Error && e.name !== 'AbortError') setError(e.message)
      } finally { if (!controller.signal.aborted) setLoading(false) }
    }, 220)
    return () => { controller.abort(); clearTimeout(timer) }
  }, [parameters])
  useEffect(() => {
    const dialog = help.current
    if (helpOpen) dialog?.showModal()
    else dialog?.close()
  }, [helpOpen])
  function update<K extends keyof Parameters>(key: K, value: Parameters[K]) { setParameters(p => ({ ...p, [key]: value })) }
  function chooseSolid(id:string) {
    setParameters(p=>({...p,solid_id:id,preset_id:null,face_transforms:{}}))
    setSelectedFaceId(null)
  }
  function choosePreset(id:string) {
    const preset=presets.find(p=>p.id===id)
    setSelectedFaceId(null)
    setParameters(p=>({...p,solid_id:preset?.solid_id ?? p.solid_id,preset_id:preset?.id ?? null,face_transforms:{},apex_offset_mm:preset?.solid_id==='tetrahedron' || preset?.solid_id==='octahedron' ? p.edge_length_mm/15 : p.edge_length_mm/6}))
  }
  function changeFace(mode:FaceTransform['mode'],offset:number,equivalent=false) {
    if (!design) return
    const face=design.base_faces.find(f=>f.id===(selectedFaceId ?? 'F001')) ?? design.base_faces[0]
    const transforms:Record<string,FaceTransform>=Object.fromEntries(design.base_faces.map(f=>[f.id,f.transform]))
    for (const f of design.base_faces) if (f.id===face.id || (equivalent && f.sides===face.sides)) transforms[f.id]={mode,offset_mm:offset}
    setParameters(p=>({...p,preset_id:null,face_transforms:transforms}))
  }
  function saveProject() {
    if (!design || loading || error) return
    const data={format:'solids-studio',version:2,geometry_version:2,solid_registry_version:1,parameters:design.parameters}
    const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}))
    const a=document.createElement('a');a.href=url;a.download=`${parameters.preset_id ?? parameters.solid_id}.solids.json`;a.click()
    setTimeout(()=>URL.revokeObjectURL(url),1000)
  }
  async function loadProject(file?:File) {
    if (!file) return
    try {
      if (file.size>1000000) throw new Error('This project file is too large.')
      const data=JSON.parse(await file.text())
      if (!data || typeof data!=='object' || Array.isArray(data)) throw new Error('Choose a Solids project JSON file.')
      if (data.format && data.format!=='solids-studio') throw new Error('This is not a Solids project file.')
      if (data.version && ![1,2].includes(data.version)) throw new Error('This project version is not supported.')
      if (data.geometry_version && data.geometry_version>2) throw new Error('This project uses a newer geometry version.')
      if (data.solid_registry_version && data.solid_registry_version!==1) throw new Error('This project uses an unsupported solid registry version.')
      const loaded={...defaults,...(data.parameters ?? data)}
      const response=await fetch('/api/design',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(loaded)})
      if (!response.ok) throw new Error(await responseError(response))
      setSelectedFaceId(null);setParameters(loaded)
    } catch (e) {setExportError(e instanceof Error ? e.message : 'Could not load that project.')}
    if (loadInput.current) loadInput.current.value=''
  }
  async function download(kind: 'pdf' | 'svg' | 'calibration', id?: string) {
    if (!design || loading || error || design.export_error) return
    setExporting(true)
    setExportError('')
    try {
      const r = await fetch(`/api/export/${kind}${id ? `/${id}` : ''}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(design.parameters) })
      if (!r.ok) throw new Error(await responseError(r))
      const url = URL.createObjectURL(await r.blob())
      const a = document.createElement('a')
      a.href = url; a.download = kind==='calibration' ? 'convex-reflex-calibration.pdf' : `${design.parameters.preset_id ?? design.parameters.solid_id}-${id ?? 'templates'}.${kind}`
      document.body.appendChild(a); a.click(); a.remove()
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (e) { setExportError(e instanceof Error ? e.message : 'The download failed. Please try again.') }
    finally { setExporting(false) }
  }
  const panel = design?.templates.find(t => t.id === selected) ?? design?.templates[0]
  const edge = selectedEdge !== null ? design?.edges[selectedEdge] : null
  const valid = !!design && !error && !loading && !design.export_error
  const selectedBase=design?.base_faces.find(f=>f.id===(selectedFaceId ?? 'F001')) ?? design?.base_faces[0]
  const faceTransform=parameters.face_transforms[selectedBase?.id ?? ''] ?? selectedBase?.transform ?? {mode:'flat',offset_mm:0}
  const transformSupported=catalog.find(s=>s.id===parameters.solid_id)?.transform_supported
  const parentOptions=design?.base_faces ?? []
  return <>
    <header className="masthead">
      <a href="/" className="wordmark" aria-label="Solids home"><svg viewBox="0 0 32 34" aria-hidden="true"><path d="M16 2 30 10 30 25 16 33 2 25 2 10Z M2 10 16 18 30 10 M16 18V33 M16 2V18 M2 25 16 18 30 25" /></svg>solids<span className="wordmark-dot">.</span></a>
      <span className="masthead-note">A TOOL FOR SLOW MAKING</span>
      <button className="text-button" onClick={() => setHelpOpen(true)}>The cutting guide <MoveUpRight size={14}/></button>
    </header>
    <main>
      <section className="intro">
        <div><div className="eyebrow"><span className="status-dot"/> THE CERAMIC TEMPLATE STUDIO</div><h1>A solid start<span>.</span></h1><p>Pick a form. Dial in your clay. Make every edge meet.</p></div>
        <div className="intro-note"><Ruler size={18}/><span>Made for real dimensions.<br/><strong>And a little patience.</strong></span></div>
      </section>
      <div className="workbench">
        <aside className="settings" aria-label="Template settings">
          <div className="section-label"><span>01 / THE FORM</span><Box size={15}/></div>
          <label className="field-label" htmlFor="solid">Choose your solid</label>
          <div className="select-wrap"><select id="solid" value={parameters.solid_id} onChange={e => chooseSolid(e.target.value)}>
            {!catalog.length && <option value={parameters.solid_id}>Rhombicuboctahedron</option>}
            {['Archimedean', 'Platonic'].map(family => <optgroup key={family} label={`${family} solids`}>{catalog.filter(s => s.family.toLowerCase() === family.toLowerCase()).map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</optgroup>)}
          </select><ChevronDown size={14}/></div>
          <p className="field-hint">{design ? `${design.total_faces} faces · ${design.total_edges} edges · ${design.templates.length} unique panels` : '13 Archimedean + 5 Platonic solids'}</p>
          <label className="field-label" htmlFor="preset">Construction recipe</label>
          <div className="select-wrap"><select id="preset" value={parameters.preset_id ?? ''} onChange={e=>choosePreset(e.target.value)}><option value="">Original / custom faces</option>{presets.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select><ChevronDown size={14}/></div>
          {parameters.preset_id && <div className="apex-control"><label className="field-label" htmlFor="apex-offset">Apex depth / height <span>fired mm</span></label><input id="apex-offset" type="number" min="0" max="2000" step="1" value={Number.isFinite(parameters.apex_offset_mm) ? parameters.apex_offset_mm : ''} onChange={e=>update('apex_offset_mm',e.target.valueAsNumber)}/><input aria-label="Recipe apex offset slider" type="range" min="0" max={presets.find(p=>p.id===parameters.preset_id)?.mode==='inward' ? Math.max(1,Math.floor(Math.min(...parentOptions.map(f=>f.recess_limit_mm))* .95)) : parameters.edge_length_mm} step="0.5" value={parameters.apex_offset_mm} onChange={e=>update('apex_offset_mm',+e.target.value)}/><p className="field-hint">Offset from each original face plane. Shrinkage is applied once.</p></div>}
          {transformSupported && <details ref={faceEditor} className="face-editor"><summary>Edit individual faces <span>{selectedFaceId ?? 'select a face'}</span></summary>
            <label className="field-label" htmlFor="face-id">Original face</label><div className="select-wrap"><select id="face-id" value={selectedFaceId ?? parentOptions[0]?.id ?? ''} onChange={e=>setSelectedFaceId(e.target.value)}>{parentOptions.map(f=><option key={f.id} value={f.id}>{f.id} · {polygonName[f.sides] ?? `${f.sides} sides`}</option>)}</select><ChevronDown size={13}/></div>
            <label className="field-label" htmlFor="face-mode">Face transformation</label><div className="select-wrap"><select id="face-mode" value={faceTransform.mode} onChange={e=>changeFace(e.target.value as FaceTransform['mode'],faceTransform.offset_mm || parameters.edge_length_mm/15)}><option value="flat">Flat</option><option value="inward">Recess / inward pyramid</option><option value="outward">Extrude / outward pyramid</option></select><ChevronDown size={13}/></div>
            {faceTransform.mode!=='flat' && <><label className="field-label" htmlFor="face-offset">{faceTransform.mode==='inward' ? 'Recess depth' : 'Extrude height'} <span>fired mm</span></label><input id="face-offset" type="number" min="0" max="2000" step="0.5" value={Number.isFinite(faceTransform.offset_mm) ? faceTransform.offset_mm : ''} onChange={e=>changeFace(faceTransform.mode,e.target.valueAsNumber)}/><input aria-label="Face apex offset slider" type="range" min="0" max={faceTransform.mode==='inward' ? Math.max(1,(selectedBase?.recess_limit_mm ?? 60)*.95) : parameters.edge_length_mm} step="0.5" value={faceTransform.offset_mm} onChange={e=>changeFace(faceTransform.mode,+e.target.value)}/></>}
            <button className="face-action" onClick={()=>changeFace(faceTransform.mode,faceTransform.offset_mm,true)}>Apply to all {polygonName[selectedBase?.sides ?? 4]?.toLowerCase() ?? 'equivalent'} faces</button>
            <button className="face-action secondary" onClick={()=>setParameters(p=>({...p,preset_id:null,face_transforms:{}}))}><RotateCcw size={12}/> Reset transformations</button>
            <p className="field-hint">Click a face in 3D to select its parent. Apexes use the original regular face centroid.</p>
          </details>}
          <div className="setting-divider"/>
          <div className="section-label"><span>02 / YOUR CLAY</span><Ruler size={15}/></div>
          <label className="field-label" htmlFor="edge">{design?.phase2 ? 'Finished base edge' : 'Finished exterior edge'} <span>mm</span></label>
          <input id="edge" type="number" min="1" max="2000" step="1" value={Number.isFinite(parameters.edge_length_mm) ? parameters.edge_length_mm : ''} onChange={e => update('edge_length_mm', e.target.valueAsNumber)}/>
          <p className="field-hint">{design?.phase2 ? 'Original base edge after firing. New panel edges are calculated.' : 'Your desired size after firing.'}</p>
          <div className="field-pair">
            <div><label className="field-label" htmlFor="thickness">Slab thickness <span>mm</span></label><input id="thickness" type="number" min="0.1" max="100" step="0.5" value={Number.isFinite(parameters.thickness_mm) ? parameters.thickness_mm : ''} onChange={e => update('thickness_mm', e.target.valueAsNumber)}/></div>
            <div><label className="field-label" htmlFor="shrinkage">Shrinkage <span>%</span></label><input id="shrinkage" type="number" min="0" max="99" step="0.5" value={Number.isFinite(parameters.shrinkage_percent) ? parameters.shrinkage_percent : ''} onChange={e => update('shrinkage_percent', e.target.valueAsNumber)}/></div>
          </div>
          <p className="field-hint">Working-clay thickness. Cut-to-fired shrinkage.</p>
          <div className="working-edge"><span>{design?.phase2 ? 'Working base reference edge' : 'Cut your working edge at'}</span><strong>{design ? design.cut_edge_mm.toFixed(2) : '—'} <small>mm</small></strong>{parameters.shrinkage_percent > 0 && <span className="compensated"><Check size={12}/> Shrinkage compensated</span>}</div>
          <div className="setting-divider"/>
          <div className="section-label"><span>03 / THE PAPER</span><Layers3 size={15}/></div>
          <div className="field-pair paper-fields"><div><label className="field-label" htmlFor="paper">Paper size</label><div className="select-wrap"><select id="paper" value={parameters.page_format} onChange={e => update('page_format', e.target.value as Parameters['page_format'])}><option value="letter">US Letter</option><option value="a4">A4</option><option value="a3">A3</option></select><ChevronDown size={13}/></div></div>
          <div><label className="field-label" htmlFor="precision">Angle decimals</label><div className="select-wrap"><select id="precision" value={parameters.angle_precision} onChange={e => update('angle_precision', +e.target.value)}>{[0,1,2,3,4].map(n => <option key={n} value={n}>{n} decimals</option>)}</select><ChevronDown size={13}/></div></div></div>
          <button className="download-button" disabled={!valid || exporting} onClick={() => download('pdf')}>{exporting ? <LoaderCircle size={17} className="spin"/> : <ArrowDownToLine size={17}/>} {exporting ? 'Preparing your file…' : 'Download templates'}<ArrowRight size={16}/></button>
          <p className="download-note">Vector PDF · {design?.layout.page_count ?? '—'} sheets · actual size</p>
          {design?.phase2 && <p className="tile-note">Includes {design.layout.assembly_pages} assembly sheet{design.layout.assembly_pages===1 ? '' : 's'}. Experimental plan: test a convex/reflex joint first.</p>}
          {design?.phase2 && <button className="face-action secondary" disabled={!valid || exporting} onClick={()=>download('calibration')}>Download 60° test coupons</button>}
          {design?.layout.tiled && <p className="tile-note">Oversized panels are tiled with 10 mm overlap and alignment marks.</p>}
          <button className="reset-settings" onClick={() => setParameters(defaults)}><RotateCcw size={12}/> Reset to studio defaults</button>
          <div className="project-actions"><button disabled={!design || loading || !!error} onClick={saveProject}>Save project</button><button onClick={()=>loadInput.current?.click()}>Load project</button><input ref={loadInput} aria-label="Load project file" type="file" accept=".json,application/json" hidden onChange={e=>loadProject(e.target.files?.[0])}/></div>
        </aside>
        <section className={`preview ${loading ? 'is-loading' : ''}`} aria-label="Design preview">
          <div className="preview-toolbar"><div className="view-tabs" role="tablist" aria-label="Preview mode"><button role="tab" aria-selected={view === 'solid'} className={view === 'solid' ? 'active' : ''} onClick={() => setView('solid')}><Box size={14}/> 3D solid</button><button role="tab" aria-selected={view === 'panels'} className={view === 'panels' ? 'active' : ''} onClick={() => setView('panels')}><Layers3 size={14}/> Flat panels</button></div><button className="icon-button" title="Reset view" aria-label="Reset view" onClick={() => { setResetKey(n => n + 1); setSelected(null); setSelectedEdge(null) }}><RotateCcw size={15}/></button></div>
          <div className="viewport">
            <div className="viewport-tag">{view === 'solid' ? 'ASSEMBLED FORM' : `TEMPLATE ${panel?.id ?? 'A'} / ${exteriorView ? 'EXTERIOR' : 'INTERIOR'} FACE UP`}</div>
            {design && view === 'solid' && <SolidView design={design} selected={selected} selectedFaceId={selectedFaceId} resetKey={resetKey} onFace={fi => { setSelected(design.templates.find(t => t.face_ids.includes(fi))?.id ?? null); setSelectedEdge(null);setSelectedFaceId(design.face_records[fi].source_face_id);if(faceEditor.current) faceEditor.current.open=true }} onEdge={ei => { setSelectedEdge(ei); setSelected(null) }}/ >}
            {design && view === 'panels' && panel && <div className="flat-view"><Panel template={panel} large exterior={exteriorView}/><div className="panel-switcher">{design.templates.map(t => <button key={t.id} className={panel.id === t.id ? 'active' : ''} onClick={() => setSelected(t.id)}>{t.id}</button>)}<button className="face-view-toggle" onClick={()=>setExteriorView(v=>!v)}>{exteriorView ? 'View interior' : 'View exterior'}</button></div></div>}
            {!design && <div className="initial-loading"><LoaderCircle className="spin" size={25}/><span>Finding the right angles…</span></div>}
            {loading && design && <div className="updating"><LoaderCircle size={12} className="spin"/> Updating</div>}
            {design && <div className="viewport-name"><span>{design.name}</span><small>{view === 'solid' ? 'Drag to rotate · Scroll to zoom · Click to inspect' : `${panel?.sides}-sided panel · Make ${panel?.quantity} · Preview is not to scale`}</small></div>}
            <span className="axis-marker" aria-hidden="true"><svg width="42" height="42" viewBox="0 0 42 42"><path d="M20 25V6M20 25 37 32M20 25 4 34" fill="none" stroke="#929783"/><text x="18" y="5">Y</text><text x="36" y="39">X</text><text x="0" y="41">Z</text></svg></span>
          </div>
          <div className="preview-bottom">
            <div className="section-label">THE JOINT SETTINGS <span className="muted">/ FROM SLAB PLANE</span></div>
            <div className="joint-types">{design?.edge_types.map(type => <button key={type.id} className="joint" onClick={() => setSelectedEdge(design.edges.findIndex(e => e.category === type.id))}><span className={`joint-dot ${type.edge_kind}`} style={{ background: COLORS[type.id % COLORS.length] }}/><span>{type.adjacent_sides.map(n => polygonName[n] ?? `${n}-gon`).join(' ↔ ')}<strong>{type.angle_deg.toFixed(parameters.angle_precision)}<span>°</span></strong>{design.phase2 && <small>{type.edge_kind} · {type.cut_side==='exterior' ? 'OUT / exterior up' : 'IN / interior up'}</small>}</span></button>)}</div>
            {design?.phase2 && <p className="edge-legend">Solid 3D edges: convex / dashed 3D edges: concave. IN and OUT identify the side facing up for that cut.</p>}
            {edge && <div className="inspector"><span><strong>{edge.id} / {edge.angle_deg.toFixed(parameters.angle_precision)}° tool setting</strong> · {edge.dihedral_deg.toFixed(4)}° interior dihedral · {(90 - edge.angle_deg).toFixed(4)}° from perpendicular{design?.phase2 && <><br/>{edge.edge_kind} · {edge.cut_side.toUpperCase()} FACE UP · {edge.face_ids.join(' ↔ ')} · {edge.length_mm.toFixed(2)} mm reference edge</>}</span><button aria-label="Close edge details" className="icon-button" onClick={() => setSelectedEdge(null)}><X size={13}/></button></div>}
          </div>
        </section>
      </div>
      <div aria-live="polite">{error && <p className="error-message" role="alert">{error} The previous preview is retained; export is disabled.</p>}{exportError && <p className="error-message" role="alert">{exportError}</p>}{design?.export_error && <p className="error-message" role="alert">{design.export_error}</p>}{design?.warnings.filter(w=>w!==design.export_error).map(w => <p className="warning-message" key={w}>{w}</p>)}</div>
      {design && <section className="template-library" aria-label="Reusable panel templates">
        <div className="library-heading"><div><div className="eyebrow">FROM FORM TO FLAT</div><h2>Your panels, ready to make<span>.</span></h2></div><span>{design.templates.length} templates <span className="muted">/</span> {design.total_faces} pieces in clay</span></div>
        <div className="template-grid">{design.templates.map(t => <article className={`template-card ${selected === t.id ? 'selected' : ''}`} key={t.id}>
          <div className="card-top"><span className="template-id">{t.id}</span><span className="quantity">MAKE {t.quantity}</span></div>
          <button className="panel-select" aria-label={`Inspect template ${t.id}`} onClick={() => { setSelected(t.id); setSelectedEdge(null); setView('panels') }}><Panel template={t}/><span className="inspect-label"><Expand size={12}/> Inspect panel</span></button>
          <div className="card-bottom"><div><h3>{polygonName[t.sides] ?? `${t.sides}-sided panel`}</h3><p>{design.phase2 ? `${t.edges.map(e=>e.length_mm.toFixed(2)).join(' · ')} mm reference edges` : `${design.cut_edge_mm.toFixed(2)} mm per exterior edge`}</p></div><button className="svg-button" disabled={!valid || exporting} onClick={() => download('svg', t.id)} aria-label={`Download template ${t.id} as SVG`} title="Download actual-size SVG">SVG <Download size={12}/></button></div>
          <div className="orientation-label">{design.phase2 ? 'INTERIOR VIEW / EXTENDED BLANK' : 'INTERIOR UP / EXTERIOR DOWN'} <span>{design.phase2 ? '· IN: interior up / OUT: exterior up' : '· Cut, then bevel from above'}</span></div>
        </article>)}</div>
      </section>}
      <section className="making-note"><div className="note-number">90<span>°</span></div><div><h3>{design?.phase2 ? 'Follow the cut side.' : 'Interior up. Exterior down.'}</h3><p>{design?.phase2 ? 'IN edges: interior face up. OUT edges: exterior face up. Cut the extended blank first, then follow each edge’s instruction. Reflex joints trim the exterior extension back to the reference outline. Test a convex/reflex scrap joint before making the shell.' : 'Keep the exterior face down throughout cutting and beveling. Cut the full outline, then remove upper waste from the interior face, preserving the exterior edge underneath. Settings are from the slab plane: 90° is perpendicular, 0° is parallel.'}</p><BevelerNote/></div><button className="text-button" onClick={() => setHelpOpen(true)}>See the cutting guide <MoveUpRight size={14}/></button></section>
      <footer><span>solids. <span className="muted">A little geometry for your clay practice.</span></span><span>Measure twice. Make slowly.</span></footer>
    </main>
    <dialog ref={help} onCancel={() => setHelpOpen(false)} onClick={e => { if (e.target === help.current) setHelpOpen(false) }} aria-labelledby="guide-title"><div className="dialog-top"><span className="eyebrow">AT THE WORKBENCH</span><button className="icon-button" aria-label="Close cutting guide" onClick={() => setHelpOpen(false)}><X size={20}/></button></div><h2 id="guide-title">{design?.phase2 ? <>IN or OUT?<br/><em>Keep the reference.</em></> : <>Interior face up.<br/><em>Exterior face down.</em></>}</h2>
      {design?.phase2 && <div className="phase2-guide"><p><strong>IN = interior face up. OUT = exterior face up.</strong> Mixed panels need cuts from both sides. Both settings are angles from the slab plane, with 90° normal to it.</p><p>Trace the solid <strong>extended blank</strong>, with the interior up. Keep the template ID and transfer edge IDs before turning the clay over. For OUT edges, remove upper exterior waste back to the <strong>dash-dot exterior reference</strong>. The dashed polygon is the final interior surface.</p><svg viewBox="0 0 420 135" className="section-diagram" role="img" aria-label="Exterior-up cut for reflex joint: upper exterior waste is removed from the extended blank, with the enlarged interior face underneath."><path d="M100 35H350V95H65Z" fill="#ddd7c7" stroke="#535d4b"/><path d="M65 35H100L65 95Z" fill="#d99b78" stroke="#a75d3b" strokeDasharray="4 4"/><text x="120" y="20">OUT: EXTERIOR FACE UP</text><text x="110" y="117">INTERIOR DOWN / extended edge</text><text x="0" y="52">upper waste</text></svg><p><strong>Calibration first:</strong> at 6 mm working thickness, a convex 120° joint and a reflex 240° joint both use a 60° tool setting. The former insets the interior edge 3.4641 mm; the latter needs a 3.4641 mm outward extension. Dry-fit both in scrap before committing a full set.</p><p>Solid outline = blank. Dash-dot = exterior reference. Dashed = interior surface. Dimensions on the PDF refer to the reference edges, not the expanded blank. Finite-thickness intersections block export.</p></div>}
      <svg className="section-diagram" viewBox="0 0 460 190" role="img" aria-label="Cutting and beveling position: interior face up, exterior face down. Remove the upper waste wedge and preserve the lower exterior edge."><path d="M115 65 350 65 350 135 80 135Z" fill="#ddd7c7" stroke="#535d4b" strokeWidth="1.5"/><path d="M80 65H115L80 135Z" fill="#d99b78" fillOpacity=".25" stroke="#a75d3b" strokeDasharray="4 4"/><path d="M80 135 115 65" stroke="#a75d3b" strokeWidth="3"/><path d="M35 135H395" stroke="#89917c" strokeDasharray="3 5"/><text x="180" y="45">INTERIOR / face up</text><text x="95" y="165">EXTERIOR / face down — preserve this edge</text><path d="M98 135A18 18 0 0 0 88 119" fill="none" stroke="#a75d3b"/><text x="105" y="126">θ</text><text x="5" y="82" fill="#a75d3b">upper waste</text><path d="M62 87 88 83" stroke="#a75d3b"/><text x="270" y="105">working slab</text></svg>
      <BevelerNote detailed/>
      {!design?.phase2 && <ol><li><strong>Roll your clay.</strong> Use its working thickness and total linear shrinkage from cutting to fired.</li><li><strong>Print at 100% / Actual Size.</strong> Disable Fit to Page. Measure the PDF’s 100 mm ruler and 1-inch square.</li><li><strong>Cut with the exterior face down.</strong> Keep the interior face up and trace the full solid outline onto it. This is the full exterior footprint before beveling. Cut the shape and make the labeled quantity.</li><li><strong>Bevel in that same position.</strong> Keep the exterior face down and the interior face up throughout cutting and beveling. Remove the upper waste at each labeled tool angle, preserving the exterior edge underneath. The dashed polygon shows the remaining upper interior face.</li><li><strong>Test a scrap joint.</strong> Tool settings describe ideal geometry; clay moisture, scoring, slip, and wire movement affect the fit.</li></ol>}
      <p className="guide-footnote">For tiled panels, align matching registration crosses in the 10 mm overlap. Join the complete outline before tracing. Never mirror a chiral template.</p>
      <button className="download-button" onClick={() => setHelpOpen(false)}>Back to the studio <ArrowRight size={16}/></button>
    </dialog>
  </>
}

createRoot(document.getElementById('root')!).render(<StrictMode><App/></StrictMode>)
