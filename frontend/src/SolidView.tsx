import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import type { Design } from './types'
import { COLORS } from './types'
import {fittingSites} from './fitting'
import type {FittingSite} from './fitting'

export function SolidView({design,selected,selectedFaceId,selectedEdgeId,selectedCategory,fittingSite,focusRequest,showDimensions,resetKey,onFace,onEdge,onFitting}: {
  design:Design;selected:string|null;selectedFaceId:string|null;selectedEdgeId:string|null;selectedCategory:number|null
  fittingSite:FittingSite|null;focusRequest:number;showDimensions:boolean;resetKey:number
  onFace:(face:number)=>void;onEdge:(edge:number)=>void;onFitting:(key:string)=>void
}) {
  const host = useRef<HTMLDivElement>(null)
  const [failed, setFailed] = useState(false)
  const lastFocusRequest=useRef(0)
  const previousDimensions=useRef(false)
  const previousDistance=useRef<number|null>(null)
  const cameraPosition = useRef<[number, number, number]>([3.6, 2.7, 4.4])
  const lastResetKey = useRef(resetKey)
  const lastRecipe = useRef('')
  const callbacks = useRef({ onFace, onEdge, onFitting })
  callbacks.current = { onFace, onEdge, onFitting }
  useEffect(() => {
    if (!host.current) return
    let renderer: THREE.WebGLRenderer
    try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }) }
    catch { setFailed(true); return }
    setFailed(false)
    const element = host.current
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.setClearColor(0x000000, 0)
    renderer.outputColorSpace = THREE.SRGBColorSpace
    element.appendChild(renderer.domElement)
    renderer.domElement.setAttribute('aria-label', 'Rotatable 3D solid. Drag to orbit, scroll to zoom, click a face or edge to inspect.')
    renderer.domElement.setAttribute('role', 'img')
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(32, 1, 0.01, 100)
    const recipe = `${design.parameters.solid_id}:${design.parameters.preset_id ?? ''}`
    const reset = lastResetKey.current !== resetKey
    if (reset || (lastRecipe.current !== recipe && design.parameters.preset_id === 'excavated-cube-single')) {
      let position = new THREE.Vector3(3.6, 2.7, 4.4)
      // Look into the excavated source face when opening the one-face recipe.
      // The first two fan edges retain the original face's outward winding.
      if (design.parameters.preset_id === 'excavated-cube-single' && design.phase2) {
        const fan = design.face_records.flatMap((r, i) => r.source_face_id === 'F001' ? [design.faces[i]] : [])
        if (fan.length >= 2) {
          const point = (i: number) => new THREE.Vector3(...design.vertices[i] as [number, number, number])
          const a = point(fan[0][0]), b = point(fan[0][1]), c = point(fan[1][1])
          const along = b.sub(a).normalize()
          const normal = new THREE.Vector3().crossVectors(along, c.sub(a)).normalize()
          const across = new THREE.Vector3().crossVectors(normal, along).normalize()
          position = normal.multiplyScalar(4.8).addScaledVector(along, 2.3).addScaledVector(across, 1.7)
        }
      }
      cameraPosition.current = position.toArray() as [number, number, number]
    }
    lastResetKey.current = resetKey
    lastRecipe.current = recipe
    if (lastFocusRequest.current!==focusRequest && fittingSite) {
      const target=new THREE.Vector3(...fittingSite.position as [number,number,number])
      if(target.length()>0)cameraPosition.current=target.normalize().multiplyScalar(6.3).toArray() as [number,number,number]
    }
    lastFocusRequest.current=focusRequest
    camera.position.set(...cameraPosition.current)
    const initialSize=element.getBoundingClientRect()
    camera.aspect=initialSize.width/Math.max(1,initialSize.height)
    camera.updateProjectionMatrix()
    if(!showDimensions && previousDimensions.current && previousDistance.current!==null)camera.position.setLength(previousDistance.current)
    if(showDimensions && !previousDimensions.current)previousDistance.current=camera.position.length()
    previousDimensions.current=showDimensions
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.enablePan = false
    controls.minDistance = 2.6
    controls.maxDistance = 10
    controls.autoRotate = false
    controls.target.set(0, 0, 0)
    scene.add(new THREE.AmbientLight(0xffffff, 2.1))
    const light = new THREE.DirectionalLight(0xffffff, 3.2)
    light.position.set(3, 5, 4)
    if (design.phase2) light.position.copy(camera.position).add(new THREE.Vector3(0, 3, 0))
    scene.add(light)
    const fill = new THREE.DirectionalLight(0xcdd6bf, 1.2)
    fill.position.set(-4, 0, -2)
    scene.add(fill)
    const original = design.vertices.map(v => new THREE.Vector3(...v as [number, number, number]))
    const scale = 1.35 / Math.max(...original.map(v => v.length()))
    const points = original.map(v => v.multiplyScalar(scale))
    const group = new THREE.Group()
    scene.add(group)
    const pickFaces: THREE.Mesh[] = []
    const pickEdges: THREE.Line[] = []
    const pickCollisions: THREE.Mesh[] = []
    const collisions=design.thickness_check?.collisions ?? []
    const collisionFaces=new Set(collisions.flatMap(c=>c.faces))
    const faceColors: Record<number, string> = { 3: '#be825f', 4: '#c9c9b4', 5: '#bfbd91', 6: '#aabcae', 8: '#b5c2c2', 10: '#c3b4a3' }
    const selectedFaces = new Set(selectedFaceId ? design.face_records.flatMap((r,i) => r.source_face_id===selectedFaceId ? [i] : []) : design.templates.find(t => t.id === selected)?.face_ids ?? [])
    design.faces.forEach((face, fi) => {
      const positions: number[] = []
      for (let i = 1; i < face.length - 1; i++) {
        for (const vi of [face[0], face[i], face[i + 1]]) positions.push(...points[vi].toArray())
      }
      const geometry = new THREE.BufferGeometry()
      geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
      geometry.computeVertexNormals()
      const material = new THREE.MeshStandardMaterial({ color: collisionFaces.has(fi) ? (selectedFaces.has(fi) ? '#cd8c8c' : '#e4aaaa') : selectedFaces.has(fi) ? '#cc9a67' : faceColors[face.length] ?? '#c6b8a4',
        roughness: 0.93, metalness: 0, flatShading: true, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 })
      const mesh = new THREE.Mesh(geometry, material)
      mesh.userData.faceIndex = fi
      group.add(mesh)
      pickFaces.push(mesh)
    })
    design.edges.forEach((edge, ei) => {
      const geometry = new THREE.BufferGeometry().setFromPoints(edge.vertices.map(vi => points[vi]))
      const material = edge.edge_kind==='concave' ? new THREE.LineDashedMaterial({color:COLORS[edge.category%COLORS.length],dashSize:.06,gapSize:.025}) : new THREE.LineBasicMaterial({ color: COLORS[edge.category % COLORS.length], linewidth: 2 })
      const line = new THREE.Line(geometry, material)
      line.computeLineDistances()
      line.userData.edgeIndex = ei
      group.add(line)
      pickEdges.push(line)
      if (edge.id===selectedEdgeId || edge.category===selectedCategory) {
        const curve=new THREE.LineCurve3(points[edge.vertices[0]],points[edge.vertices[1]])
        const highlight=new THREE.Mesh(new THREE.TubeGeometry(curve,1,.009,6,false),new THREE.MeshBasicMaterial({color:'#304c35'}))
        group.add(highlight)
      }
    })
    const sites=fittingSites(design)
    for (const site of sites) {
      const marker=new THREE.Mesh(new THREE.SphereGeometry(site.key===fittingSite?.key ? .033 : .024,12,8),new THREE.MeshBasicMaterial({color:site.key===fittingSite?.key ? '#87322f' : '#a94444'}))
      marker.position.set(...site.position.map(v=>v*scale) as [number,number,number])
      marker.userData.siteKey=site.key
      marker.userData.collisionDetail=`${site.collisionIds.join(' / ')} · ${site.faceIds.join(' ↔ ')}. After beveling, manually shape this corner to fit.`
      group.add(marker);pickCollisions.push(marker)
    }
    if(collisions.length)renderer.domElement.setAttribute('aria-label',`Rotatable 3D solid. ${collisionFaces.size} pale red faces need manual corner fitting; ${sites.length} marked overlap locations. Click a red dot for panel references. Drag to orbit, scroll to zoom.`)
    const dimensionLabels:{element:HTMLSpanElement;point:THREE.Vector3}[]=[]
    let dimensionRadius=0
    const fitDimensions=()=>{
      if(!dimensionRadius)return
      const halfFov=Math.atan(Math.tan(THREE.MathUtils.degToRad(camera.fov/2))*Math.min(1,camera.aspect))
      const distance=dimensionRadius/Math.sin(halfFov)*1.12
      controls.maxDistance=Math.max(10,distance*1.1)
      if(camera.position.length()<distance)camera.position.setLength(distance)
    }
    if(showDimensions) {
      const box=new THREE.Box3().setFromPoints(points)
      group.add(new THREE.Box3Helper(box,0x879178))
      const mid=box.getCenter(new THREE.Vector3()),lo=box.min,hi=box.max
      dimensionRadius=Math.hypot(Math.max(Math.abs(lo.x),Math.abs(hi.x)),Math.max(Math.abs(lo.y),Math.abs(hi.y)),Math.max(Math.abs(lo.z),Math.abs(hi.z)))
      fitDimensions()
      const labels=[['W',0,new THREE.Vector3(mid.x,lo.y-.1,hi.z)],['D',1,new THREE.Vector3(hi.x+.1,lo.y,mid.z)],['H',2,new THREE.Vector3(hi.x+.1,mid.y,hi.z)]] as const
      for(const [label,index,point] of labels) {
        const element=document.createElement('span');element.className='dimension-label'
        element.textContent=`${label} ${design.dimensions.fired_mm[index].toFixed(1)} mm`
        element.setAttribute('aria-hidden','true');host.current.appendChild(element)
        dimensionLabels.push({element,point})
      }
    }
    const raycaster = new THREE.Raycaster()
    raycaster.params.Line = { threshold: 0.025 }
    let startX = 0, startY = 0
    const down = (e: PointerEvent) => { startX = e.clientX; startY = e.clientY }
    const up = (e: PointerEvent) => {
      if (Math.hypot(e.clientX - startX, e.clientY - startY) > 5) return
      const rect = renderer.domElement.getBoundingClientRect()
      raycaster.setFromCamera(new THREE.Vector2((e.clientX - rect.left) / rect.width * 2 - 1, -(e.clientY - rect.top) / rect.height * 2 + 1), camera)
      const face = raycaster.intersectObjects(pickFaces)[0]
      const edge = raycaster.intersectObjects(pickEdges)[0]
      const collision=raycaster.intersectObjects(pickCollisions)[0]
      if (collision && (!face || collision.distance<face.distance+.025)) callbacks.current.onFitting(collision.object.userData.siteKey)
      else if (edge && (!face || edge.distance < face.distance + 0.05)) callbacks.current.onEdge(edge.object.userData.edgeIndex)
      else if (face) callbacks.current.onFace(face.object.userData.faceIndex)
    }
    renderer.domElement.addEventListener('pointerdown', down)
    renderer.domElement.addEventListener('pointerup', up)
    const hover = (e: PointerEvent) => {
      if (e.buttons) return
      const rect=renderer.domElement.getBoundingClientRect()
      raycaster.setFromCamera(new THREE.Vector2((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1),camera)
      const face=raycaster.intersectObjects(pickFaces)[0]
      const edge=raycaster.intersectObjects(pickEdges)[0]
      const collision=raycaster.intersectObjects(pickCollisions)[0]
      if (collision && (!face || collision.distance<face.distance+.025)) renderer.domElement.title=collision.object.userData.collisionDetail
      else if (edge && (!face || edge.distance < face.distance+.05)) {
        const data=design.edges[edge.object.userData.edgeIndex]
        renderer.domElement.title=`${data.id}: ${data.angle_deg.toFixed(design.parameters.angle_precision)}° · ${data.cut_side.toUpperCase()} UP · ${data.edge_kind} · ${data.face_ids.join(' ↔ ')}`
      } else if (face) {
        const fi=face.object.userData.faceIndex
        renderer.domElement.title=design.face_records[fi].id+(collisionFaces.has(fi) ? ' · Marked corners need manual shaping after beveling.' : '')
      } else renderer.domElement.title=''
    }
    renderer.domElement.addEventListener('pointermove',hover)
    const resize = new ResizeObserver(() => {
      const { width, height } = element.getBoundingClientRect()
      if (!width || !height) return
      renderer.setSize(width, height)
      camera.aspect = width / height
      camera.updateProjectionMatrix()
      fitDimensions()
    })
    resize.observe(element)
    let frame = 0
    const animate = () => {
      frame=requestAnimationFrame(animate);controls.update();renderer.render(scene,camera)
      const occupied:{x:number;y:number;w:number;h:number}[]=[]
      for(const {element:label,point} of dimensionLabels) {
        const p=point.clone().project(camera)
        const w=label.offsetWidth,h=label.offsetHeight
        let x=0,y=0
        for(const offset of [0,-h-5,h+5,-2*(h+5),2*(h+5)]) {
          x=Math.max(w/2+4,Math.min(element.clientWidth-w/2-4,(p.x+1)*element.clientWidth/2))
          y=Math.max(h/2+4,Math.min(element.clientHeight-h/2-4,(1-p.y)*element.clientHeight/2+offset))
          if(!occupied.some(r=>Math.abs(x-r.x)<(w+r.w)/2+3 && Math.abs(y-r.y)<(h+r.h)/2+3))break
        }
        occupied.push({x,y,w,h})
        label.style.transform=`translate(${x}px,${y}px) translate(-50%,-50%)`
        label.style.visibility=p.z>=-1 && p.z<=1 ? 'visible' : 'hidden'
      }
    }
    animate()
    return () => {
      cameraPosition.current = camera.position.toArray() as [number, number, number]
      cancelAnimationFrame(frame)
      resize.disconnect()
      controls.dispose()
      renderer.domElement.removeEventListener('pointerdown', down)
      renderer.domElement.removeEventListener('pointerup', up)
      renderer.domElement.removeEventListener('pointermove',hover)
      scene.traverse(object => {
        if (object instanceof THREE.Mesh || object instanceof THREE.Line) {
          object.geometry.dispose()
          if (Array.isArray(object.material)) object.material.forEach(m => m.dispose())
          else object.material.dispose()
        }
      })
      dimensionLabels.forEach(({element})=>element.remove())
      renderer.dispose()
      renderer.domElement.remove()
    }
  },[design,selected,selectedFaceId,selectedEdgeId,selectedCategory,fittingSite,focusRequest,showDimensions,resetKey])
  return <div ref={host} className="solid-canvas">{failed && <div className="webgl-message">3D needs WebGL in this browser. Your panel previews and exports are still available.</div>}</div>
}
