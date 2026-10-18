import type { Design } from './types'

export type FittingSite = { key: string; position: number[]; collisionIds: string[]; faceIds: string[]; faceIndices: number[] }
const sub=(a:number[],b:number[])=>a.map((v,i)=>v-b[i])
const dot=(a:number[],b:number[])=>a.reduce((sum,v,i)=>sum+v*b[i],0)

export function fittingSites(design:Design):FittingSite[] {
  const sites=new Map<string,FittingSite>()
  for (const collision of design.thickness_check?.collisions ?? []) {
    const shared=collision.shared_vertices
    let position:number[]
    if (shared.length===1) position=design.vertices[shared[0]]
    else {
      const center=[0,1,2].map(i=>collision.region_mm.reduce((sum,p)=>sum+p[i],0)/collision.region_mm.length)
      if (shared.length===2) {
        const a=design.vertices[shared[0]],along=sub(design.vertices[shared[1]],a)
        const t=Math.max(0,Math.min(1,dot(sub(center,a),along)/dot(along,along)))
        position=a.map((v,i)=>v+t*along[i])
      } else {
        const face=design.faces[collision.faces[0]],a=design.vertices[face[0]]
        const u=sub(design.vertices[face[1]],a),v=sub(design.vertices[face[2]],a)
        const normal=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
        const distance=dot(sub(center,a),normal)/dot(normal,normal)
        position=center.map((v,i)=>v-distance*normal[i])
      }
    }
    const key=shared.length===1 ? `vertex-${shared[0]}` : position.map(v=>v.toFixed(5)).join(',')
    let site=sites.get(key)
    if (!site) {site={key,position,collisionIds:[],faceIds:[],faceIndices:[]};sites.set(key,site)}
    site.collisionIds.push(collision.id)
    collision.face_ids.forEach(id=>{if(!site.faceIds.includes(id))site.faceIds.push(id)})
    collision.faces.forEach(id=>{if(!site.faceIndices.includes(id))site.faceIndices.push(id)})
  }
  return [...sites.values()]
}
