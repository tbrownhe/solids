import { Box, Check, ChevronDown, RotateCcw, Ruler } from 'lucide-react'
import type { Design, Parameters, Preset, Solid } from './types'

export type UpdateParameters = <K extends keyof Parameters>(key:K,value:Parameters[K])=>void
export const polygonName:Record<number,string>={3:'Triangle',4:'Square',5:'Pentagon',6:'Hexagon',8:'Octagon',10:'Decagon'}
export const constructionLabel=(p:Preset)=>p.mode==='outward' ? 'Outward pyramids' : p.scope==='one' ? 'Recess one face' : 'Recess all faces'

export function DesignerControls({parameters,design,catalog,presets,update,chooseSolid,choosePreset,editFaces,reset}: {
  parameters:Parameters;design:Design|null;catalog:Solid[];presets:Preset[];update:UpdateParameters
  chooseSolid:(id:string)=>void;choosePreset:(id:string)=>void;editFaces:()=>void;reset:()=>void
}) {
  const available=presets.filter(p=>p.solid_id===parameters.solid_id)
  const preset=available.find(p=>p.id===parameters.preset_id)
  const custom=Object.values(parameters.face_transforms).some(t=>t.mode!=='flat' && t.offset_mm>0) || !!parameters.preset_id && Object.keys(parameters.face_transforms).length>0
  const supported=catalog.find(s=>s.id===parameters.solid_id)?.transform_supported
  const recessLimit=Math.min(...(design?.base_faces.map(f=>f.recess_limit_mm) ?? [60]))
  return <>
    <div className="section-label"><span>Shape</span><Box size={16}/></div>
    <label className="field-label" htmlFor="solid">Solid</label>
    <div className="select-wrap"><select id="solid" value={parameters.solid_id} onChange={e=>chooseSolid(e.target.value)}>
      {!catalog.length && <option value={parameters.solid_id}>Rhombicuboctahedron</option>}
      {['Platonic','Archimedean'].map(family=><optgroup key={family} label={`${family} solids`}>{catalog.filter(s=>s.family.toLowerCase()===family.toLowerCase()).map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</optgroup>)}
    </select><ChevronDown size={15}/></div>
    {(available.length>0 || custom) ? <>
      <label className="field-label" htmlFor="preset">Construction</label>
      <div className="select-wrap"><select id="preset" value={custom ? 'custom' : parameters.preset_id ?? ''} onChange={e=>choosePreset(e.target.value)}>
        <option value="">Original</option>
        {available.map(p=><option key={p.id} value={p.id}>{constructionLabel(p)}</option>)}
        {custom && <option value="custom" disabled>Custom faces</option>}
      </select><ChevronDown size={15}/></div>
    </> : <p className="field-hint original-form">Original form{supported ? ' · individual face edits available' : ''}</p>}
    {preset && !custom && <div className="apex-control">
      <label className="field-label" htmlFor="apex-offset">{preset.mode==='inward' ? 'Recess depth' : 'Point height'} <span>fired mm</span></label>
      <div className="offset-input"><input id="apex-offset" type="number" min="0" max="2000" step="0.5" value={Number.isFinite(parameters.apex_offset_mm) ? parameters.apex_offset_mm : ''} onChange={e=>update('apex_offset_mm',e.target.valueAsNumber)}/>
      <input aria-label="Recipe apex offset slider" type="range" min="0" max={preset.mode==='inward' ? Math.max(1,recessLimit*.95) : parameters.edge_length_mm} step="0.5" value={parameters.apex_offset_mm} onChange={e=>update('apex_offset_mm',+e.target.value)}/></div>
    </div>}
    {supported && <button className="edit-faces-button" onClick={editFaces}>Edit individual faces <span>↗</span></button>}
    <div className="setting-divider"/>
    <div className="section-label"><span>Size &amp; clay</span><Ruler size={16}/></div>
    <label className="field-label" htmlFor="edge">Base edge after firing <span>mm</span></label>
    <input id="edge" type="number" min="1" max="2000" step="1" value={Number.isFinite(parameters.edge_length_mm) ? parameters.edge_length_mm : ''} onChange={e=>update('edge_length_mm',e.target.valueAsNumber)}/>
    <p className="field-hint">{design?.phase2 ? 'Original solid’s edge. New panel edges are calculated.' : 'The desired exterior edge of each panel.'}</p>
    <div className="field-pair">
      <div><label className="field-label" htmlFor="thickness">Slab thickness <span>mm</span></label><input id="thickness" type="number" min="0.1" max="100" step="0.5" value={Number.isFinite(parameters.thickness_mm) ? parameters.thickness_mm : ''} onChange={e=>update('thickness_mm',e.target.valueAsNumber)}/></div>
      <div><label className="field-label" htmlFor="shrinkage">Shrinkage <span>%</span></label><input id="shrinkage" type="number" min="0" max="99" step="0.5" value={Number.isFinite(parameters.shrinkage_percent) ? parameters.shrinkage_percent : ''} onChange={e=>update('shrinkage_percent',e.target.valueAsNumber)}/></div>
    </div>
    <p className="field-hint">Roller setpoint in working clay. Total cut-to-fired shrinkage.</p>
    <div className="working-edge"><span>Working base edge</span><strong>{design ? design.cut_edge_mm.toFixed(2) : '—'} <small>mm</small></strong>{parameters.shrinkage_percent>0 && <span className="compensated"><Check size={12}/> Shrinkage compensated</span>}</div>
    <button className="reset-settings" onClick={reset}><RotateCcw size={13}/> Reset to studio defaults</button>
  </>
}
