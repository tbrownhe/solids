export type Parameters = {
  solid_id: string
  edge_length_mm: number
  thickness_mm: number
  shrinkage_percent: number
  page_format: 'letter' | 'a4' | 'a3'
  angle_precision: number
  preset_id: string | null
  apex_offset_mm: number
  face_transforms: Record<string, FaceTransform>
}
export type FaceTransform = { mode: 'flat' | 'inward' | 'outward'; offset_mm: number }
export type Preset = { id: string; name: string; solid_id: string; mode: 'inward' | 'outward'; scope: 'one' | 'all' }
export type BaseFace = { id: string; index: number; sides: number; transform: FaceTransform; recess_limit_mm: number }
export type FaceRecord = { id: string; source_face_id: string; base_face_index: number; subface_index: number | null }
export type Solid = { id: string; name: string; family: string; face_count: number; vertex_count: number; chirality?: string; transform_supported: boolean }
export type Edge = { id: string; vertices: number[]; faces: number[]; face_ids: string[]; angle_deg: number; dihedral_deg: number; category: number; adjacent_sides: number[]; edge_kind: 'convex' | 'concave' | 'flat'; cut_side: 'interior' | 'exterior'; signed_fold_deg: number; length_mm: number }
export type PanelEdge = { label: string; angle_deg: number; dihedral_deg: number; adjacent_sides: number; length_mm: number; category: number; inset_mm: number; exterior_offset_mm: number; cut_side: 'interior' | 'exterior'; edge_kind: string }
export type Annotation = { text: string; center: number[]; angle: number; font: number; corners: number[][] }
export type Template = { id: string; quantity: number; sides: number; polygon_mm: number[][]; reference_polygon_mm: number[][]; edges: PanelEdge[]; inset_polygon_mm: number[][]; face_ids: number[]; annotations: Annotation[]; center_annotations: (Annotation & {bold: boolean})[]; warnings: string[]; phase2: boolean }
export type Design = {
  parameters: Parameters; name: string; cut_edge_mm: number; total_faces: number; total_edges: number
  phase2: boolean; geometry_version: number; base_faces: BaseFace[]; face_records: FaceRecord[]; thickness_check: {status: string; panel_count: number} | null
  vertices: number[][]; faces: number[][]; edges: Edge[]; templates: Template[]; warnings: string[]; export_error: string | null
  edge_types: { id: number; angle_deg: number; dihedral_deg: number; adjacent_sides: number[]; edge_kind: string; cut_side: 'interior' | 'exterior' }[]
  layout: { page_count: number; tiled: boolean; overlap_mm: number; assembly_pages: number }
}
export const COLORS = ['#a75d3b', '#6c7c57', '#557f92', '#906d94', '#a38a36']
