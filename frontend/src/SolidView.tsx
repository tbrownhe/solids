import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import type { Design } from './types'
import { COLORS } from './types'

export function SolidView({ design, selected, resetKey, onFace, onEdge }: {
  design: Design; selected: string | null; resetKey: number
  onFace: (face: number) => void; onEdge: (edge: number) => void
}) {
  const host = useRef<HTMLDivElement>(null)
  const [failed, setFailed] = useState(false)
  const cameraPosition = useRef<[number, number, number]>([3.6, 2.7, 4.4])
  const lastResetKey = useRef(resetKey)
  const callbacks = useRef({ onFace, onEdge })
  callbacks.current = { onFace, onEdge }
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
    if (lastResetKey.current !== resetKey) {
      cameraPosition.current = [3.6, 2.7, 4.4]
      lastResetKey.current = resetKey
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
    const faceColors: Record<number, string> = { 3: '#be825f', 4: '#c9c9b4', 5: '#bfbd91', 6: '#aabcae', 8: '#b5c2c2', 10: '#c3b4a3' }
    const selectedFaces = new Set(design.templates.find(t => t.id === selected)?.face_ids ?? [])
    design.faces.forEach((face, fi) => {
      const positions: number[] = []
      for (let i = 1; i < face.length - 1; i++) {
        for (const vi of [face[0], face[i], face[i + 1]]) positions.push(...points[vi].toArray())
      }
      const geometry = new THREE.BufferGeometry()
      geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3))
      geometry.computeVertexNormals()
      const material = new THREE.MeshStandardMaterial({ color: selectedFaces.has(fi) ? '#cc9a67' : faceColors[face.length] ?? '#c6b8a4',
        roughness: 0.93, metalness: 0, flatShading: true, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 })
      const mesh = new THREE.Mesh(geometry, material)
      mesh.userData.faceIndex = fi
      group.add(mesh)
      pickFaces.push(mesh)
    })
    design.edges.forEach((edge, ei) => {
      const geometry = new THREE.BufferGeometry().setFromPoints(edge.vertices.map(vi => points[vi]))
      const line = new THREE.Line(geometry, new THREE.LineBasicMaterial({ color: COLORS[edge.category % COLORS.length], linewidth: 2 }))
      line.userData.edgeIndex = ei
      group.add(line)
      pickEdges.push(line)
    })
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
      if (edge && (!face || edge.distance < face.distance + 0.05)) callbacks.current.onEdge(edge.object.userData.edgeIndex)
      else if (face) callbacks.current.onFace(face.object.userData.faceIndex)
    }
    renderer.domElement.addEventListener('pointerdown', down)
    renderer.domElement.addEventListener('pointerup', up)
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
  }, [design, selected, resetKey])
  return <div ref={host} className="solid-canvas">{failed && <div className="webgl-message">3D needs WebGL in this browser. Your panel previews and exports are still available.</div>}</div>
}
