import type { Template } from './types'
import { COLORS } from './types'

export function Panel({ template, large = false, exterior = false }: { template: Template; large?: boolean; exterior?: boolean }) {
  const points = template.polygon_mm
  const w = Math.max(...points.map(p => p[0]))
  const h = Math.max(...points.map(p => p[1]))
  const border = Math.max(w, h) * 0.14
  const viewX = (x: number) => exterior ? w-x : x
  const flip = (p: number[]) => `${viewX(p[0])},${h - p[1]}`
  return <svg className={`panel-svg ${large ? 'large' : ''}`} viewBox={`${-border} ${-border} ${w + border * 2} ${h + border * 2}`} role="img" aria-label={`Template ${template.id}, ${template.sides} sides, make ${template.quantity}`}>
    <polygon points={points.map(flip).join(' ')} fill="#efeee4" stroke="#485446" strokeWidth={w * 0.003} strokeLinejoin="round" />
    {template.inset_polygon_mm.length > 0 && <polygon points={template.inset_polygon_mm.map(flip).join(' ')} fill="none" stroke="#8c9581" strokeWidth={w * 0.002} strokeDasharray={`${w * 0.012} ${w * 0.012}`} />}
    {template.phase2 && template.edges.some(e => e.exterior_offset_mm > 0.00001) && <polygon points={template.reference_polygon_mm.map(flip).join(' ')} fill="none" stroke="#6c7973" strokeWidth={w * .002} strokeDasharray={`${w*.02} ${w*.006} ${w*.004} ${w*.006}`}/>}
    {points.map((a, i) => {
      const b = points[(i + 1) % points.length]
      return <line key={i} x1={viewX(a[0])} y1={h - a[1]} x2={viewX(b[0])} y2={h - b[1]} stroke={COLORS[template.edges[i].category % COLORS.length]} strokeWidth={w * 0.005} />
    })}
    {template.annotations.map((label, i) => {
      if (template.phase2) return <text key={i} transform={`translate(${viewX(label.center[0])} ${h-label.center[1]}) rotate(${exterior ? label.angle : -label.angle})`} textAnchor="middle" dominantBaseline="central" fontSize={label.font/(72/25.4)} fill={COLORS[template.edges[i].category%COLORS.length]} fontFamily="Arial,sans-serif">{label.text}</text>
      // Screen labels are larger than print labels. Export positions and
      // physical dimensions come from the separately tested print pipeline.
      const a = points[i], b = points[(i + 1) % points.length]
      const dx = b[0] - a[0], dy = b[1] - a[1], length = Math.hypot(dx, dy)
      const size = Math.max(w, h)
      const fontSize = size * 0.043
      const inset = Math.max(size * 0.09, template.edges[i].inset_mm + fontSize * 0.65 + Math.max(1.5, size * 0.012))
      const x = (a[0] + b[0]) / 2 - dy / length * inset
      const y = (a[1] + b[1]) / 2 + dx / length * inset
      return <text key={i} transform={`translate(${viewX(x)} ${h - y}) rotate(${exterior ? label.angle : -label.angle})`} textAnchor="middle" dominantBaseline="central" fontSize={fontSize} fill={COLORS[template.edges[i].category % COLORS.length]} fontFamily="Arial,sans-serif">{label.text}</text>
    })}
    {template.phase2 ? template.center_annotations.map((label,i) => <text key={`center-${i}`} x={viewX(label.center[0])} y={h-label.center[1]} textAnchor="middle" dominantBaseline="central" fontSize={label.font/(72/25.4)} fontWeight={label.bold ? 'bold' : 'normal'} fill="#536348">{exterior && label.text.includes('INTERIOR VIEW') ? label.text.replace('INTERIOR VIEW','EXTERIOR VIEW') : label.text}</text>) : <>
      <text x={viewX(points.reduce((sum, p) => sum + p[0], 0) / points.length)} y={h - points.reduce((sum, p) => sum + p[1], 0) / points.length - h * .035} textAnchor="middle" dominantBaseline="central" fontSize={w * .065} fontWeight="600" fill="#536348">MAKE {template.quantity}</text>
      {w > 35 && <text x={viewX(points.reduce((sum, p) => sum + p[0], 0) / points.length)} y={h - points.reduce((sum, p) => sum + p[1], 0) / points.length + h * .04} textAnchor="middle" dominantBaseline="central" fontSize={w * 0.037} fill="#727967" letterSpacing={w * 0.004}>{exterior ? 'EXTERIOR UP' : 'INTERIOR UP'}</text>}
    </>}
  </svg>
}
