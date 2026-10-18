import { useEffect, useState } from 'react'
import { ChevronDown, ChevronUp, RotateCcw } from 'lucide-react'
import { polygonName } from './DesignerControls'
import type { Design, FaceTransform, Parameters } from './types'
import { COLORS } from './types'
import type { FittingSite } from './fitting'

export type InspectorTab='selection'|'joints'|'fitting'
export function DesignerInspector({design,parameters,tab,setTab,selectedFaceId,selectedInstanceId,selectedEdge,selectedCategory,supported,selectParent,changeFace,resetTransforms,showTemplate,selectCategory,sites,siteIndex,reviewSite,editFirst}: {
  design:Design;parameters:Parameters;tab:InspectorTab;setTab:(tab:InspectorTab)=>void
  selectedFaceId:string|null;selectedInstanceId:string|null;selectedEdge:number|null;selectedCategory:number|null;supported:boolean
  selectParent:(id:string)=>void;changeFace:(mode:FaceTransform['mode'],offset:number,all?:boolean)=>void
  resetTransforms:()=>void;showTemplate:(id:string)=>void;selectCategory:(id:number)=>void
  sites:FittingSite[];siteIndex:number;reviewSite:(index:number)=>void;editFirst:()=>void
}) {
  const [collapsed,setCollapsed]=useState(false)
  useEffect(()=>setCollapsed(false),[tab,selectedFaceId,selectedInstanceId,selectedEdge,selectedCategory,siteIndex])
  const base=design.base_faces.find(f=>f.id===selectedFaceId)
  const transform=parameters.face_transforms[base?.id ?? ''] ?? base?.transform ?? {mode:'flat',offset_mm:0}
  const selectedRecord=design.face_records.find(f=>f.id===selectedInstanceId) ?? design.face_records.find(f=>f.source_face_id===selectedFaceId)
  const instanceIndex=design.face_records.findIndex(f=>f.id===selectedRecord?.id)
  const template=design.templates.find(t=>t.face_ids.includes(instanceIndex>=0 ? instanceIndex : design.face_records.findIndex(f=>f.source_face_id===selectedFaceId)))
  const edge=selectedEdge===null ? null : design.edges[selectedEdge]
  const site=sites[siteIndex]
  const tabs:InspectorTab[]=['selection','joints','fitting']
  return <section className={`workspace-inspector ${collapsed ? 'is-collapsed' : ''}`} aria-label="Design details">
    <div className="inspector-heading"><div className="inspector-tabs" role="tablist" aria-label="Design details" onKeyDown={e=>{
      const index=tabs.indexOf(tab),next=e.key==='ArrowRight' ? (index+1)%3 : e.key==='ArrowLeft' ? (index+2)%3 : e.key==='Home' ? 0 : e.key==='End' ? 2 : -1
      if(next>=0){e.preventDefault();setTab(tabs[next]);document.getElementById(`inspector-tab-${tabs[next]}`)?.focus()}
    }}>{tabs.map(id=><button key={id} id={`inspector-tab-${id}`} role="tab" aria-selected={tab===id} aria-controls={`inspector-panel-${id}`} tabIndex={tab===id ? 0 : -1} onClick={()=>{setCollapsed(false);setTab(id)}}>{id==='selection' ? 'Selection' : id==='joints' ? 'Joint settings' : <>Fitting <span className={sites.length ? 'fit-count' : ''}>{sites.length}</span></>}</button>)}</div><button className="inspector-toggle" aria-expanded={!collapsed} aria-label={collapsed ? 'Show design details' : 'Expand model'} title={collapsed ? 'Show design details' : 'Expand model by hiding details'} onClick={()=>setCollapsed(v=>!v)}>{collapsed ? <ChevronUp size={17}/> : <ChevronDown size={17}/>}</button></div>
    <div id="inspector-panel-selection" role="tabpanel" aria-labelledby="inspector-tab-selection" className="inspector-content" hidden={collapsed || tab!=='selection'} tabIndex={0}>
      {edge ? <div className="edge-detail inspector">
        <div><strong>{edge.id} · {edge.angle_deg.toFixed(parameters.angle_precision)}° wire setting</strong><p>{edge.cut_side==='interior' ? 'IN · interior face up' : 'OUT · exterior face up'} · {edge.edge_kind} joint</p></div>
        <dl><div><dt>Reference length</dt><dd>{edge.length_mm.toFixed(2)} mm</dd></div><div><dt>Interior dihedral</dt><dd>{edge.dihedral_deg.toFixed(2)}°</dd></div></dl>
        <p className="selected-reference">{edge.face_ids.join(' ↔ ')} · angle from slab plane, 90° is square.</p>
      </div> : base ? <div className="selected-face-editor">
        <div className="selection-meta"><strong>{selectedRecord?.id ?? base.id}{template && ` · Template ${template.id}`}</strong><span>Parent {base.id} · {polygonName[base.sides] ?? `${base.sides}-sided face`}</span>{template && <button className="text-button" onClick={()=>showTemplate(template.id)}>View template {template.id} ↗</button>}</div>
        <div className="face-fields">
          <div><label className="field-label" htmlFor="face-id">Original face</label><div className="select-wrap"><select id="face-id" value={base.id} onChange={e=>selectParent(e.target.value)}>{design.base_faces.map(f=><option key={f.id} value={f.id}>{f.id} · {polygonName[f.sides] ?? `${f.sides} sides`}</option>)}</select><ChevronDown size={14}/></div></div>
          {supported && <><div><label className="field-label" htmlFor="face-mode">Transformation</label><div className="select-wrap"><select id="face-mode" value={transform.mode} onChange={e=>changeFace(e.target.value as FaceTransform['mode'],transform.offset_mm || parameters.edge_length_mm/15)}><option value="flat">Flat</option><option value="inward">Recess inward</option><option value="outward">Outward pyramid</option></select><ChevronDown size={14}/></div></div>
          {transform.mode!=='flat' && <div><label className="field-label" htmlFor="face-offset">{transform.mode==='inward' ? 'Recess depth' : 'Point height'} <span>fired mm</span></label><input id="face-offset" type="number" min="0" max="2000" step="0.5" value={Number.isFinite(transform.offset_mm) ? transform.offset_mm : ''} onChange={e=>changeFace(transform.mode,e.target.valueAsNumber)}/></div>}</>}
        </div>
        {supported && <div className="face-actions"><button className="face-action" onClick={()=>changeFace(transform.mode,transform.offset_mm,true)}>Apply to all {polygonName[base.sides]?.toLowerCase() ?? 'equivalent'} faces</button><button className="face-action secondary" onClick={resetTransforms}><RotateCcw size={12}/> Reset transformations</button></div>}
      </div> : <div className="empty-selection"><strong>Select a face or edge in the model.</strong><p>Inspect its panel, bevel setting and cutting side here.</p>{supported && <button className="edit-faces-button" onClick={editFirst}>Choose a face to edit ↗</button>}</div>}
    </div>
    <div id="inspector-panel-joints" role="tabpanel" aria-labelledby="inspector-tab-joints" className="inspector-content" hidden={collapsed || tab!=='joints'} tabIndex={0}>
      <table className="joint-table"><caption>Wire angles from the slab plane · 90° is square. Select a row to highlight its edges.</caption><thead><tr><th>Joint</th><th>Wire angle</th><th>Face up</th><th>Edges</th></tr></thead><tbody>{design.edge_types.map(type=><tr key={type.id} className={selectedCategory===type.id ? 'active' : ''} onClick={()=>selectCategory(type.id)}><td><button className="joint" aria-pressed={selectedCategory===type.id} aria-label={`Highlight joint type ${type.id+1}`}><span className="joint-dot" style={{background:COLORS[type.id%COLORS.length]}}/><span><b>{type.id+1}</b> · {type.adjacent_sides.map(n=>polygonName[n] ?? `${n}-gon`).join(' ↔ ')}<small>{type.edge_kind==='concave' ? 'reflex' : type.edge_kind}</small></span></button></td><td className="joint-angle">{type.angle_deg.toFixed(parameters.angle_precision)}°</td><td><span className="cut-side">{type.cut_side==='interior' ? 'IN' : 'OUT'}</span> {type.cut_side}</td><td>{design.edges.filter(e=>e.category===type.id).length}</td></tr>)}</tbody></table>
    </div>
    <div id="inspector-panel-fitting" role="tabpanel" aria-labelledby="inspector-tab-fitting" className="inspector-content" hidden={collapsed || tab!=='fitting'} tabIndex={0}>
      {site ? <div className="fitting-detail"><div className="fitting-heading"><strong>Corner {siteIndex+1} of {sites.length}</strong><div><button disabled={siteIndex===0} onClick={()=>reviewSite(siteIndex-1)} aria-label="Previous fitting corner">← Previous</button><button disabled={siteIndex===sites.length-1} onClick={()=>reviewSite(siteIndex+1)} aria-label="Next fitting corner">Next →</button></div></div><p className="fitting-instruction">After beveling, manually shape the marked corners so the panels fit together. These warnings do not mean assembly is impossible.</p><p>Pale red faces need fitting; red dots mark the locations.</p><p className="selected-reference">{site.faceIds.map((id,i)=><span key={id}>{i>0 && ' · '}{id} / {design.templates.find(t=>t.face_ids.includes(site.faceIndices[i]))?.id}</span>)}</p><p className="field-hint">PDF overlap references: {site.collisionIds.join(', ')}</p></div> : <div className="empty-selection"><strong>{design.thickness_check ? 'No thick-panel overlaps detected.' : 'Test a scrap joint before making the shell.'}</strong><p>Clay moisture, cutting and joining affect the real fit. Check the printed scale and dry-fit your panels.</p></div>}
    </div>
  </section>
}
