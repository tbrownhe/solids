import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import type { Design } from './types'
import { COLORS } from './types'

export function SolidView({ design, selected, selectedFaceId, resetKey, onFace, onEdge }: {
  design: Design; selected: string | null; selectedFaceId: string | null; resetKey: number
  onFace: (face: number) => void; onEdge: (edge: number) => void
}) {
  const host = useRef<HTMLDivElement>(null)
  const [failed, setFailed] = useState(false)
  const [collisionDetail,setCollisionDetail]=useState('')
  const [focusCorners,setFocusCorners]=useState(0)
  const lastFocusCorners=useRef(0)
  const cameraPosition = useRef<[number, number, number]>([3.6, 2.7, 4.4])
  const lastResetKey = useRef(resetKey)
  const lastRecipe = useRef('')
  const callbacks = useRef({ onFace, onEdge })
  callbacks.current = { onFace, onEdge }
  useEffect(() => {
    if (!host.current) return
    let renderer: THREE.WebGLRenderer
    try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }) }
    catch { setFailed(true); return }
    setFailed(false)
    setCollisionDetail('')
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
    if (lastFocusCorners.current!==focusCorners) {
      const regions=design.thickness_check?.collisions.flatMap(c=>c.region_mm) ?? []
      const target=regions.reduce((sum,p)=>sum.add(new THREE.Vector3(...p as [number,number,number])),new THREE.Vector3())
      if (target.length()<1e-5 && regions.length) target.set(...regions[0] as [number,number,number])
      if (target.length()>0) cameraPosition.current=target.normalize().multiplyScalar(6.3).toArray() as [number,number,number]
      lastFocusCorners.current=focusCorners
    }
    camera.position.set(...cameraPosition.current)
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
    })
    const sites=new Map<string,{position:THREE.Vector3;ids:string[];faces:Set<string>}>()
    for (const collision of collisions) {
      let position:THREE.Vector3
      if (collision.shared_vertices.length===1) position=points[collision.shared_vertices[0]].clone()
      else {
        const center=new THREE.Vector3()
        collision.region_mm.forEach(p=>center.add(new THREE.Vector3(...p as [number,number,number])))
        center.multiplyScalar(scale/collision.region_mm.length)
        if (collision.shared_vertices.length===2) {
          position=new THREE.Line3(points[collision.shared_vertices[0]],points[collision.shared_vertices[1]]).closestPointToPoint(center,true,new THREE.Vector3())
        } else {
          const face=design.faces[collision.faces[0]]
          position=new THREE.Plane().setFromCoplanarPoints(points[face[0]],points[face[1]],points[face[2]]).projectPoint(center,new THREE.Vector3())
        }
      }
      const key=position.toArray().map(v=>v.toFixed(5)).join(',')
      let site=sites.get(key)
      if (!site) {site={position,ids:[],faces:new Set()};sites.set(key,site)}
      site.ids.push(collision.id)
      collision.face_ids.forEach(id=>site.faces.add(id))
    }
    for (const site of sites.values()) {
      const marker=new THREE.Mesh(new THREE.SphereGeometry(.024,12,8),new THREE.MeshBasicMaterial({color:'#a94444'}))
      marker.position.copy(site.position)
      marker.userData.collisionDetail=`${site.ids.join(' / ')} · ${[...site.faces].join(' ↔ ')}. After beveling, manually shape this corner to fit.`
      group.add(marker);pickCollisions.push(marker)
    }
    if (collisions.length) renderer.domElement.setAttribute('aria-label',`Rotatable 3D solid. ${collisionFaces.size} pale red faces need manual corner fitting; ${sites.size} marked overlap locations. Click a red dot for panel references. Drag to orbit, scroll to zoom.`)
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
      if (collision && (!face || collision.distance<face.distance+.025)) setCollisionDetail(collision.object.userData.collisionDetail)
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
    })
    resize.observe(element)
    let frame = 0
    const animate = () => { frame = requestAnimationFrame(animate); controls.update(); renderer.render(scene, camera) }
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
      renderer.dispose()
      renderer.domElement.remove()
    }
  }, [design, selected, selectedFaceId, resetKey, focusCorners])
  return <div ref={host} className="solid-canvas">{failed && <div className="webgl-message">3D needs WebGL in this browser. Your panel previews and exports are still available.</div>}{!!design.thickness_check?.collisions.length && !failed && <button type="button" className="focus-corners" onClick={()=>setFocusCorners(n=>n+1)}>View fitting areas</button>}{collisionDetail && <div className="collision-callout" role="status"><span>{collisionDetail}</span><button type="button" aria-label="Close overlap details" onClick={()=>setCollisionDetail('')}>×</button></div>}</div>
}
