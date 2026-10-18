import {lazy,Suspense,useEffect,useMemo,useRef,useState} from 'react'
import {ArrowDownToLine,ArrowRight,Box,ChevronDown,Download,Expand,Layers3,LoaderCircle,MoveUpRight,Printer,RotateCcw,Ruler,Settings2,X} from 'lucide-react'
import {Panel} from './Panel'
import {BevelerNote} from './BevelerNote'
import {DesignerControls,constructionLabel,polygonName} from './DesignerControls'
import {DesignerInspector} from './DesignerInspector'
import type {InspectorTab} from './DesignerInspector'
import {fittingSites} from './fitting'
import type {Design,Parameters,Solid,Preset,FaceTransform} from './types'
import type {KeyboardEvent} from 'react'

const SolidView=lazy(()=>import('./SolidView').then(module=>({default:module.SolidView})))
const defaults:Parameters={solid_id:'rhombicuboctahedron',edge_length_mm:120,thickness_mm:6,shrinkage_percent:0,page_format:'letter',angle_precision:2,preset_id:null,apex_offset_mm:20,face_transforms:{}}
function keepDialogFocus(event:KeyboardEvent<HTMLDialogElement>) {
  if(event.key!=='Tab')return
  const fields=[...event.currentTarget.querySelectorAll<HTMLElement>('button:not([disabled]),input:not([disabled]),select:not([disabled]),summary,a[href],[tabindex="0"]')].filter(el=>el.getClientRects().length>0)
  const first=fields[0],last=fields.at(-1)
  if(event.shiftKey && document.activeElement===first){event.preventDefault();last?.focus()}
  else if(!event.shiftKey && document.activeElement===last){event.preventDefault();first?.focus()}
}
function readParameters():Parameters {
  try {const value=JSON.parse(localStorage.getItem('solids.parameters') ?? 'null');return value ? {...defaults,...(value.parameters ?? value)} : defaults} catch{return defaults}
}
async function responseError(response:Response) {
  const data=await response.json().catch(()=>({}))
  if(typeof data.detail==='string')return data.detail
  if(Array.isArray(data.detail)) {
    const names:Record<string,string>={solid_id:'Solid',edge_length_mm:'Base edge',thickness_mm:'Slab thickness',shrinkage_percent:'Shrinkage',apex_offset_mm:'Point height or depth',offset_mm:'Face height or depth',page_format:'Paper size',angle_precision:'Angle decimals'}
    return data.detail.map((d:{loc:string[];msg:string})=>`${names[d.loc.at(-1) ?? ''] ?? 'Setting'}: ${d.msg}`).join('; ')
  }
  return `Could not complete the request (${response.status}).`
}
export function Designer({onDesign,onOpenHelp}:{onDesign:(design:Design)=>void;onOpenHelp:()=>void}) {
  const [parameters, setParameters] = useState<Parameters>(defaults)
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
  const loadInput=useRef<HTMLInputElement>(null)
  const [narrow,setNarrow]=useState(false)
  const [controlsOpen,setControlsOpen]=useState(false)
  const [printOpen,setPrintOpen]=useState(false)
  const [inspectorTab,setInspectorTab]=useState<InspectorTab>('joints')
  const [selectedInstanceId,setSelectedInstanceId]=useState<string|null>(null)
  const [selectedCategory,setSelectedCategory]=useState<number|null>(null)
  const [siteIndex,setSiteIndex]=useState(0)
  const [focusRequest,setFocusRequest]=useState(0)
  const [showDimensions,setShowDimensions]=useState(false)
  const controlsSheet=useRef<HTMLDialogElement>(null)
  const printDialog=useRef<HTMLDialogElement>(null)
  useEffect(()=>{const media=matchMedia('(max-width:900px)');const update=()=>setNarrow(media.matches);update();media.addEventListener('change',update);return()=>media.removeEventListener('change',update)},[])
  useEffect(()=>{const sheet=controlsSheet.current;if(narrow && controlsOpen)sheet?.showModal();else sheet?.close()},[narrow,controlsOpen])
  useEffect(()=>{if(!narrow)setControlsOpen(false)},[narrow])
  useEffect(()=>{if(printOpen)printDialog.current?.showModal();else printDialog.current?.close()},[printOpen])
  useEffect(() => { setParameters(readParameters()) }, [])
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
        onDesign(result)
        setSelected(null)
        setSelectedEdge(null)
        setSelectedCategory(null)
        localStorage.setItem('solids.parameters', JSON.stringify({format:'solids-studio',version:2,geometry_version:2,parameters}))
      } catch (e) {
        if (e instanceof Error && e.name !== 'AbortError') setError(e.message)
      } finally { if (!controller.signal.aborted) setLoading(false) }
    }, 220)
    return () => { controller.abort(); clearTimeout(timer) }
  }, [parameters])
  function update<K extends keyof Parameters>(key: K, value: Parameters[K]) { setParameters(p => ({ ...p, [key]: value })) }
  function clearSelection() {
    setSelectedFaceId(null);setSelectedInstanceId(null);setSelectedEdge(null);setSelectedCategory(null);setSelected(null);setSiteIndex(0)
  }
  function chooseSolid(id:string) {
    setParameters(p=>({...p,solid_id:id,preset_id:null,face_transforms:{}}))
    clearSelection();setResetKey(n=>n+1)
  }
  function choosePreset(id:string) {
    if(id==='custom') return
    const preset=presets.find(p=>p.id===id && p.solid_id===parameters.solid_id)
    if(id && !preset) return
    clearSelection()
    setParameters(p=>({...p,preset_id:preset?.id ?? null,face_transforms:{},apex_offset_mm:preset ? (p.solid_id==='tetrahedron' || p.solid_id==='octahedron' ? p.edge_length_mm/15 : p.edge_length_mm/6) : p.apex_offset_mm}))
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
      clearSelection();setParameters(loaded)
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
  const panel=design?.templates.find(t=>t.id===selected) ?? design?.templates[0]
  const sites=useMemo(()=>design ? fittingSites(design) : [],[design])
  const activeSiteIndex=Math.min(siteIndex,Math.max(0,sites.length-1))
  const selectedSite=sites[activeSiteIndex] ?? null
  const valid=!!design && !error && !loading && !design.export_error
  const blocked=error || design?.export_error || ''
  const supported=!!catalog.find(s=>s.id===parameters.solid_id)?.transform_supported
  const recipe=presets.find(p=>p.id===parameters.preset_id)
  const custom=Object.values(parameters.face_transforms).some(t=>t.mode!=='flat' && t.offset_mm>0) || !!parameters.preset_id && Object.keys(parameters.face_transforms).length>0
  const notes=design?.warnings.filter(w=>!w.includes('thick-panel overlaps') && !w.startsWith('Construction note:')) ?? []
  function selectFace(fi:number) {
    if(!design)return
    setSelectedFaceId(design.face_records[fi].source_face_id);setSelectedInstanceId(design.face_records[fi].id)
    setSelected(design.templates.find(t=>t.face_ids.includes(fi))?.id ?? null)
    setSelectedEdge(null);setSelectedCategory(null);setInspectorTab('selection')
  }
  function editFaces() {
    setControlsOpen(false);setInspectorTab('selection');setView('solid')
    if(!selectedFaceId && design)selectFace(0)
  }
  function selectEdge(index:number) {
    setSelectedEdge(index);setSelectedFaceId(null);setSelectedInstanceId(null);setSelectedCategory(null);setSelected(null);setInspectorTab('selection')
  }
  function selectCategory(id:number) {
    setSelectedCategory(id);setSelectedEdge(null);setSelectedFaceId(null);setSelectedInstanceId(null);setSelected(null);setView('solid')
  }
  function reviewSite(index:number,focus=true) {
    setSiteIndex(index);setInspectorTab('fitting');setView('solid');setControlsOpen(false)
    setSelectedEdge(null);setSelectedCategory(null);setSelectedFaceId(null);setSelectedInstanceId(null);setSelected(null)
    if(focus)setFocusRequest(n=>n+1)
  }
  const controls=<DesignerControls parameters={parameters} design={design} catalog={catalog} presets={presets} update={update} chooseSolid={chooseSolid} choosePreset={choosePreset} editFaces={editFaces} reset={()=>{setParameters(defaults);clearSelection()}}/>
  return <>
    <h2 className="sr-only" id="designer-title">Design printable clay slab panels</h2>
    <div className="workbench workspace" id="studio" tabIndex={-1} aria-labelledby="designer-title">
      <div className="workspace-header"><h3>Your design</h3><div className="workspace-projects"><button disabled={!design || loading || !!error} onClick={saveProject}>Save project</button><button onClick={()=>loadInput.current?.click()}>Load project</button><input ref={loadInput} aria-label="Load project file" type="file" accept=".json,application/json" hidden onChange={e=>loadProject(e.target.files?.[0])}/></div></div>
      {!narrow && <aside className="settings" aria-label="Shape, size and clay">{controls}</aside>}
      <section className={`preview ${loading ? 'is-loading' : ''}`} aria-label="Design preview">
        <button className="mobile-shape-summary" aria-label="Choose shape and construction" onClick={()=>setControlsOpen(true)}><span>{catalog.find(s=>s.id===parameters.solid_id)?.name ?? 'Rhombicuboctahedron'}<small>{custom ? 'Custom faces' : recipe ? constructionLabel(recipe) : 'Original form'}</small></span><ChevronDown size={17}/></button>
        <section className="assembled-size" aria-labelledby="assembled-size-title"><div><h3 id="assembled-size-title">Estimated size after firing</h3><p>Exterior model bounds · W × D × H</p></div><dl>{(design?.dimensions.axes ?? ['width','depth','height']).map((axis,i)=><div key={axis}><dt>{axis}</dt><dd>{design ? design.dimensions.fired_mm[i].toFixed(1) : '—'} <small>mm</small></dd></div>)}</dl>{design && parameters.shrinkage_percent>0 && <p className="working-size">Before firing: {design.dimensions.working_mm.map(v=>v.toFixed(1)).join(' × ')} mm</p>}</section>
        <div className="preview-toolbar"><div className="view-tabs" role="tablist" aria-label="Preview mode" onKeyDown={e=>{if(e.key==='ArrowRight' || e.key==='ArrowLeft'){e.preventDefault();const next=view==='solid' ? 'panels' : 'solid';setView(next);document.getElementById(`view-tab-${next}`)?.focus()}}}><button id="view-tab-solid" role="tab" aria-selected={view==='solid'} aria-controls="model-view" tabIndex={view==='solid' ? 0 : -1} className={view==='solid' ? 'active' : ''} onClick={()=>setView('solid')}><Box size={15}/> 3D solid</button><button id="view-tab-panels" role="tab" aria-selected={view==='panels'} aria-controls="model-view" tabIndex={view==='panels' ? 0 : -1} className={view==='panels' ? 'active' : ''} onClick={()=>setView('panels')}><Layers3 size={15}/> Flat panels</button></div><div className="viewer-actions">{view==='solid' && <button aria-label="Show dimensions" title="Show model dimensions" className={showDimensions ? 'active' : ''} aria-pressed={showDimensions} onClick={()=>setShowDimensions(v=>!v)}><Ruler size={16}/><span>Dimensions</span></button>}<button className="icon-button" title="Reset view" aria-label="Reset view" onClick={()=>{setResetKey(n=>n+1);clearSelection()}}><RotateCcw size={17}/></button></div></div>
        <div className="viewport" id="model-view" role="tabpanel" aria-labelledby={`view-tab-${view}`}>
          <div className="viewport-tag">{view==='solid' ? 'ASSEMBLED FORM' : `TEMPLATE ${panel?.id ?? 'A'} / ${exteriorView ? 'EXTERIOR' : 'INTERIOR'} FACE UP`}</div>
          {design && view==='solid' && <Suspense fallback={<div className="initial-loading">Loading the 3D preview…</div>}><SolidView design={design} selected={selected} selectedFaceId={selectedFaceId} selectedEdgeId={selectedEdge===null ? null : design.edges[selectedEdge]?.id ?? null} selectedCategory={selectedCategory} fittingSite={inspectorTab==='fitting' ? selectedSite : null} focusRequest={focusRequest} showDimensions={showDimensions} resetKey={resetKey} onFace={selectFace} onEdge={selectEdge} onFitting={key=>{const index=sites.findIndex(s=>s.key===key);if(index>=0)reviewSite(index,false)}}/></Suspense>}
          {design && view==='panels' && panel && <div className="flat-view"><Panel template={panel} large exterior={exteriorView}/><div className="panel-switcher"><label htmlFor="display-template">Template</label><select id="display-template" value={panel.id} onChange={e=>setSelected(e.target.value)}>{design.templates.map(t=><option key={t.id} value={t.id}>{t.id} · make {t.quantity}</option>)}</select><button className="face-view-toggle" onClick={()=>setExteriorView(v=>!v)}>{exteriorView ? 'View interior' : 'View exterior'}</button></div></div>}
          {!design && <div className="initial-loading"><LoaderCircle className="spin" size={24}/><span>Finding the right angles…</span></div>}
          {loading && design && <div className="updating" role="status"><LoaderCircle size={12} className="spin"/> Updating</div>}
          {design && <div className="viewport-name"><span>{design.name}</span><small>{view==='solid' ? (narrow ? 'Drag to rotate · Pinch to zoom · Tap a face or edge' : 'Drag to rotate · Scroll to zoom · Select a face or edge') : 'Interior/exterior views · Preview is not to scale'}</small></div>}
        </div>
        <div className="workspace-status"><span>{design ? `${design.total_faces} clay panels · ${design.templates.length} reusable patterns` : 'Calculating panels…'}</span>{sites.length>0 && <button className="fit-summary" onClick={()=>reviewSite(activeSiteIndex)}><span aria-hidden="true"/> {sites.length} corners need hand fitting <b>Review →</b></button>}</div>
        {design && <DesignerInspector design={design} parameters={parameters} tab={inspectorTab} setTab={tab=>{if(tab==='fitting' && sites.length)reviewSite(activeSiteIndex);else setInspectorTab(tab)}} selectedFaceId={selectedFaceId} selectedInstanceId={selectedInstanceId} selectedEdge={selectedEdge} selectedCategory={selectedCategory} supported={supported} selectParent={id=>{setSelectedFaceId(id);setSelectedInstanceId(null);setSelectedEdge(null);setSelectedCategory(null)}} changeFace={changeFace} resetTransforms={()=>{setParameters(p=>({...p,preset_id:null,face_transforms:{}}));setSelectedInstanceId(null)}} showTemplate={id=>{setSelected(id);setView('panels')}} selectCategory={selectCategory} sites={sites} siteIndex={activeSiteIndex} reviewSite={reviewSite} editFirst={editFaces}/>}
      </section>
      <div className="workspace-export">
        {(blocked || exportError) && <p className="workspace-error" role="alert">{blocked ? `${blocked}${error ? ' The previous preview is retained.' : ''} Export is disabled.` : exportError}</p>}
        <button className="open-controls" onClick={()=>setControlsOpen(true)}><Settings2 size={17}/> Controls</button>
        <button className="print-settings-button" aria-label="Print settings" onClick={()=>setPrintOpen(true)}><Printer size={16}/><span>Print settings<small>{parameters.page_format==='letter' ? 'US Letter' : parameters.page_format.toUpperCase()}</small></span><ChevronDown size={14}/></button>
        <p className="download-note">Vector PDF · {design?.layout.page_count ?? '—'} sheets · actual size</p>
        <button className="download-button" aria-label={exporting ? 'Preparing your file…' : 'Download PDF'} disabled={!valid || exporting} onClick={()=>download('pdf')}>{exporting ? <LoaderCircle className="spin" size={17}/> : <ArrowDownToLine size={17}/>} {exporting ? 'Preparing your file…' : 'Download PDF'}<ArrowRight size={16}/></button>
      </div>
    </div>
    {narrow && <dialog ref={controlsSheet} onKeyDown={keepDialogFocus} className="controls-sheet workspace-dialog" aria-labelledby="controls-title" onCancel={()=>setControlsOpen(false)} onClick={e=>{if(e.target===controlsSheet.current)setControlsOpen(false)}}><div className="sheet-heading"><h2 id="controls-title">Shape, size &amp; clay</h2><button className="icon-button" aria-label="Close controls" onClick={()=>setControlsOpen(false)}><X size={21}/></button></div><div className="settings">{controls}</div><button className="sheet-done" onClick={()=>setControlsOpen(false)}>Done · view model <ArrowRight size={16}/></button></dialog>}
    <dialog ref={printDialog} onKeyDown={keepDialogFocus} className="print-dialog workspace-dialog" aria-labelledby="print-title" onCancel={()=>setPrintOpen(false)} onClick={e=>{if(e.target===printDialog.current)setPrintOpen(false)}}><div className="sheet-heading"><h2 id="print-title">Print settings</h2><button className="icon-button" aria-label="Close print settings" onClick={()=>setPrintOpen(false)}><X size={21}/></button></div><label className="field-label" htmlFor="paper">Paper size</label><div className="select-wrap"><select id="paper" value={parameters.page_format} onChange={e=>update('page_format',e.target.value as Parameters['page_format'])}><option value="letter">US Letter</option><option value="a4">A4</option><option value="a3">A3</option></select><ChevronDown size={15}/></div><p className="field-hint">Print at 100% / Actual Size. Measure the calibration marks before cutting.</p><details className="advanced-print"><summary>Advanced print options</summary><label className="field-label" htmlFor="precision">Angle decimals</label><div className="select-wrap"><select id="precision" value={parameters.angle_precision} onChange={e=>update('angle_precision',+e.target.value)}>{[0,1,2,3,4].map(n=><option key={n} value={n}>{n} decimals</option>)}</select><ChevronDown size={15}/></div></details><div className="print-summary"><strong>{design?.layout.page_count ?? '—'} sheets · vector PDF · actual size</strong>{design?.phase2 && <p>Includes {design.layout.assembly_pages} assembly sheet{design.layout.assembly_pages===1 ? '' : 's'}. Test a convex/reflex joint first.</p>}{!!design?.layout.collision_pages && <p>Includes {design.layout.collision_pages} overlap reference sheet{design.layout.collision_pages===1 ? '' : 's'}. Manually shape marked corners after beveling.</p>}{design?.layout.tiled && <p>Oversized panels tile with 10 mm overlap and alignment marks.</p>}</div>{design?.phase2 && <button className="coupon-button" disabled={!valid || exporting} onClick={()=>download('calibration')}>Download 60° test coupons <Download size={15}/></button>}<button className="sheet-done" onClick={()=>setPrintOpen(false)}>Done <ArrowRight size={16}/></button></dialog>
    {notes.length>0 && <details className="design-notes"><summary>Fabrication notes · {notes.length}</summary>{notes.map(note=><p key={note}>{note}</p>)}</details>}
    {design && <section className="template-library" aria-label="Reusable panel templates"><div className="library-heading"><div><div className="eyebrow">FROM FORM TO FLAT</div><h2>Your panels, ready to make<span>.</span></h2></div><span>{design.templates.length} templates <span className="muted">/</span> {design.total_faces} pieces in clay</span></div><div className="template-grid">{design.templates.map(t=><article className={`template-card ${selected===t.id ? 'selected' : ''}`} key={t.id}><div className="card-top"><span className="template-id">{t.id}</span><span className="quantity">MAKE {t.quantity}</span></div><button className="panel-select" onClick={()=>{setSelected(t.id);setSelectedFaceId(null);setSelectedInstanceId(null);setSelectedEdge(null);setSelectedCategory(null);setView('panels');document.getElementById('studio')?.scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion:reduce)').matches ? 'instant' : 'smooth'})}}><span className="panel-art" aria-hidden="true"><Panel template={t}/></span><span className="inspect-label"><Expand size={12}/> Inspect template {t.id}</span></button><div className="card-bottom"><div><h3>{polygonName[t.sides] ?? `${t.sides}-sided panel`}</h3><p>{design.phase2 ? `${t.edges.map(e=>e.length_mm.toFixed(2)).join(' · ')} mm reference edges` : `${design.cut_edge_mm.toFixed(2)} mm per exterior edge`}</p></div><button className="svg-button" disabled={!valid || exporting} onClick={()=>download('svg',t.id)} aria-label={`Download template ${t.id} as SVG`} title="Download actual-size SVG">SVG <Download size={13}/></button></div><div className="orientation-label">{design.phase2 ? 'INTERIOR VIEW / EXTENDED BLANK' : 'INTERIOR UP / EXTERIOR DOWN'} <span>{design.phase2 ? '· IN: interior up / OUT: exterior up' : '· Cut, then bevel from above'}</span></div>{t.collision_regions.length>0 && <p className="panel-collision-note">Overlap areas marked for manual relief · {t.quantity===1 ? 'this copy needs' : `all ${t.quantity} copies need`} corner shaping after beveling. Check instance IDs in the PDF reference.</p>}</article>)}</div></section>}
    <section className="making-note"><div className="note-number">90<span>°</span></div><div><h3>A note on cutting and fit.</h3><p>For convex forms, keep the exterior face down while cutting and beveling. Inverted forms may need bevels from both sides; follow the IN / OUT edge labels. Start with the solid blank outline, and try a small test joint to get a feel for the fit.</p><BevelerNote/></div><button className="text-button" onClick={onOpenHelp}>See the cutting guide <MoveUpRight size={14}/></button></section>
  </>
}
