export type Parameters = {
  solid_id: string
  edge_length_mm: number
  thickness_mm: number
  shrinkage_percent: number
  page_format: 'letter' | 'a4' | 'a3'
  angle_precision: number
}
export type Solid = { id: string; name: string; family: string; face_count: number; vertex_count: number; chirality?: string }
export type Edge = { vertices: number[]; faces: number[]; angle_deg: number; dihedral_deg: number; category: number; adjacent_sides: number[] }
export type PanelEdge = { label: string; angle_deg: number; dihedral_deg: number; adjacent_sides: number; length_mm: number; category: number; inset_mm: number }
export type Annotation = { text: string; center: number[]; angle: number; font: number; corners: number[][] }
export type Template = { id: string; quantity: number; sides: number; polygon_mm: number[][]; edges: PanelEdge[]; inset_polygon_mm: number[][]; face_ids: number[]; annotations: Annotation[]; warnings: string[] }
export type Design = {
  parameters: Parameters; name: string; cut_edge_mm: number; total_faces: number; total_edges: number
  vertices: number[][]; faces: number[][]; edges: Edge[]; templates: Template[]; warnings: string[]; export_error: string | null
  edge_types: { id: number; angle_deg: number; dihedral_deg: number; adjacent_sides: number[] }[]
  layout: { page_count: number; tiled: boolean; overlap_mm: number }
}
export const COLORS = ['#a75d3b', '#6c7c57', '#557f92', '#906d94', '#a38a36']
