"""Validated polygon topology, signed symmetric miters, and panel grouping.

Flat coordinates are millimetres of the full exterior footprint, viewed with
the INTERIOR UP and EXTERIOR DOWN for cutting and beveling. Mesh winding is
outward. Grouping uses exterior patterns and rotations only; each grouped panel
is then viewed from its interior, reversing its displayed edge order exactly
once. This viewing reflection does not merge handed patterns or reflect the solid.
"""
from functools import lru_cache
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field
from scipy.spatial import ConvexHull

from .registry import get_solid
from .mesh import analyze_mesh
from .transforms import transform_mesh
from .fabrication import signed_inset, offset_polygon, check_thick_shell


class FaceTransform(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    mode: Literal["flat", "inward", "outward"] = "flat"
    offset_mm: float = Field(default=0, ge=0, le=2000)


class Parameters(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    solid_id: str = "rhombicuboctahedron"
    preset_id: str | None = None
    apex_offset_mm: float = Field(default=20, ge=0, le=2000)
    face_transforms: dict[str, FaceTransform] = Field(default_factory=dict, max_length=120)
    edge_length_mm: float = Field(default=120, gt=0, le=2000)
    thickness_mm: float = Field(default=6, gt=0, le=100)
    shrinkage_percent: float = Field(default=0, ge=0, lt=100)
    page_format: Literal["letter", "a4", "a3"] = "letter"
    angle_precision: int = Field(default=2, ge=0, le=4)


def _unit(v):
    length = float(np.linalg.norm(v))
    if length < 1e-12:
        raise ValueError("Degenerate polygon or edge in source mesh.")
    return v / length


@lru_cache(maxsize=32)
def topology(solid_id: str) -> dict:
    source = get_solid(solid_id)
    vertices = np.asarray(source["vertices"], dtype=float)
    vertices = vertices - vertices.mean(axis=0)
    mesh = analyze_mesh(vertices, source["faces"], intersections=False)
    lengths = [edge["length_mm"] for edge in mesh["edges"]]
    edge_length = float(np.mean(lengths))
    if max(lengths)-min(lengths) > edge_length*1e-6:
        raise ValueError("Base solid does not have uniform reference edges.")
    mesh["vertices"] /= edge_length
    mesh["source"] = source
    return mesh


def inset_polygon(polygon, insets):
    """Intersect inward edge half-planes, including corner intersections.

    Convex clipping cannot produce a self-intersecting polygon. Empty/degenerate
    output means the slab is too thick for these exterior dimensions.
    """
    result = [np.array(p, dtype=float) for p in polygon]
    for i, distance in enumerate(insets):
        a, b = np.array(polygon[i]), np.array(polygon[(i + 1) % len(polygon)])
        inward = _unit(np.array([-(b - a)[1], (b - a)[0]]))
        boundary = a + inward * distance
        clipped = []
        if not result:
            break
        for p, q in zip(result, result[1:] + result[:1]):
            dp, dq = float(np.dot(p - boundary, inward)), float(np.dot(q - boundary, inward))
            if dp >= -1e-9:
                clipped.append(p)
            if (dp > 0) != (dq > 0) and abs(dp - dq) > 1e-12:
                clipped.append(p + (q - p) * dp / (dp - dq))
        result = clipped
    if len(result) < 3:
        return []
    area = abs(sum(float(p[0] * q[1] - q[0] * p[1])
                   for p, q in zip(result, result[1:] + result[:1]))) / 2
    return [p.tolist() for p in result] if area > 1e-6 else []


def collision_annotations(mesh, templates, collisions):
    """Project real 3D overlap volumes into each copy's canonical interior view."""
    copies={instance["face_index"]:(template,instance) for template in templates for instance in template["instances"]}
    for template in templates:
        template["collision_regions"]=[]
        template["collision_warnings"]=[]
        template["collision_vertices"]=[]
    for collision in collisions:
        collision["panels"]=[]
        for side,fi in enumerate(collision["faces"]):
            template,instance=copies[fi]
            points=mesh["vertices"][instance["vertex_ids"]]
            u=_unit(points[1]-points[0])
            v=np.cross(-mesh["normals"][fi],u)
            reference=np.array(template["reference_polygon_mm"])
            axis=_unit(reference[1]-reference[0]);across=np.array([-axis[1],axis[0]])
            delta=np.array(collision["region_mm"])-points[0]
            projected=reference[0]+(delta@u)[:,None]*axis+(delta@v)[:,None]*across
            hull=ConvexHull(projected)
            polygon=projected[hull.vertices]
            # A reusable type can represent copies with different neighbors.
            # Keep every case, but merge congruent marked regions for drawing.
            key=tuple(sorted(tuple(p) for p in np.round(polygon,5)))
            region=next((r for r in template["collision_regions"] if r["key"]==key),None)
            if region is None:
                region={"key":key,"polygon_mm":polygon.tolist(),"collision_ids":[],"instance_ids":[]}
                template["collision_regions"].append(region)
            region["collision_ids"].append(collision["id"])
            if instance["id"] not in region["instance_ids"]:region["instance_ids"].append(instance["id"])
            corners=[i for i,vi in enumerate(instance["vertex_ids"]) if vi in collision["shared_vertices"]]
            for i in corners:
                if i not in template["collision_vertices"]:template["collision_vertices"].append(i)
            warning={"collision_id":collision["id"],"instance_id":instance["id"],
                     "other_instance_id":collision["face_ids"][1-side],
                     "template_id":template["id"],"corner_labels":[f"V{i+1}" for i in corners]}
            template["collision_warnings"].append(warning)
            collision["panels"].append(warning)
    for template in templates:
        template["collision_vertices"].sort()
        for region in template["collision_regions"]:region.pop("key")


def make_design(parameters: Parameters) -> dict:
    base = topology(parameters.solid_id)
    cut_edge = parameters.edge_length_mm / (1 - parameters.shrinkage_percent / 100)
    if cut_edge > 5000:
        raise ValueError("Shrinkage compensation exceeds the 5,000 mm working-edge limit.")
    construction = transform_mesh(base, parameters, cut_edge)
    phase2 = construction["active"]
    records = construction["face_records"]
    vertices = construction["vertices"]
    if phase2:
        mesh = analyze_mesh(vertices, construction["faces"], face_ids=[f["id"] for f in records])
    else:
        mesh = {**base, "vertices": vertices}
    mesh["source"] = base["source"]
    edges = [dict(edge) for edge in mesh["edges"]]
    for edge in edges:
        a,b = edge["vertices"]
        edge["length_mm"] = float(np.linalg.norm(vertices[b]-vertices[a]))
        edge["face_ids"] = [records[i]["id"] for i in edge["faces"]]
    edge_lookup = {tuple(edge["vertices"]): edge for edge in edges}
    types = sorted({(tuple(e["adjacent_sides"]), round(e["angle_deg"], 8), e["edge_kind"], e["cut_side"]) for e in edges})
    for edge in edges:
        edge["category"] = types.index((tuple(edge["adjacent_sides"]), round(edge["angle_deg"], 8), edge["edge_kind"], edge["cut_side"]))
    groups = {}
    for fi, raw_face in enumerate(mesh["faces"]):
        sequence = []
        for i, a in enumerate(raw_face):
            b = raw_face[(i + 1) % len(raw_face)]
            c = raw_face[(i + 2) % len(raw_face)]
            edge = edge_lookup[tuple(sorted((a, b)))]
            # Full intrinsic outline and ordered bevel/adjacency pattern.
            length = float(np.linalg.norm(vertices[b] - vertices[a]))
            turn = float(np.dot(_unit(vertices[b] - vertices[a]), _unit(vertices[c] - vertices[b])))
            neighbor = next(f for f in edge["faces"] if f != fi)
            sequence.append((round(length / cut_edge, 8), round(turn, 8),
                             round(edge["angle_deg"], 8), len(mesh["faces"][neighbor]), edge["cut_side"]))
        start = min(range(len(sequence)), key=lambda i: tuple(sequence[i:] + sequence[:i]))
        key = tuple(sequence[start:] + sequence[:start])
        face = raw_face[start:] + raw_face[:start]
        interior_edge_order = [0] + list(range(len(face)-1,0,-1))
        joints = [edge_lookup[tuple(sorted((a,b)))]["id"] for a,b in zip(face,face[1:]+face[:1])]
        instance = {**records[fi], "face_index":fi,
                    "vertex_ids":[face[i] for i in [1,0]+list(range(len(face)-1,1,-1))],
                    "edges":[{"label":f"E{i+1}","joint_id":joints[j]} for i,j in enumerate(interior_edge_order)]}
        if key in groups:
            groups[key]["quantity"] += 1
            groups[key]["face_ids"].append(fi)
            groups[key]["instances"].append(instance)
            continue
        points = vertices[face]
        u = _unit(points[1] - points[0])
        v = np.cross(mesh["normals"][fi], u)
        xy = np.column_stack(((points - points[0]) @ u, (points - points[0]) @ v))
        xy -= xy.min(axis=0)
        panel_edges = []
        for i, a in enumerate(face):
            b = face[(i + 1) % len(face)]
            edge = edge_lookup[tuple(sorted((a, b)))]
            neighbor = next(f for f in edge["faces"] if f != fi)
            panel_edges.append({"label": f"E{i + 1}", "angle_deg": edge["angle_deg"],
                                "dihedral_deg": edge["dihedral_deg"],
                                "adjacent_sides": len(mesh["faces"][neighbor]),
                                "length_mm": float(np.linalg.norm(points[(i + 1) % len(face)] - points[i])),
                                "category": edge["category"],
                                "cut_side": edge["cut_side"], "edge_kind": edge["edge_kind"],
                                "signed_fold_deg": edge["signed_fold_deg"],
                                "signed_inset_mm": signed_inset(edge["dihedral_deg"], parameters.thickness_mm),
                                "exterior_offset_mm": max(0, -signed_inset(edge["dihedral_deg"], parameters.thickness_mm)),
                                "inset_mm": max(0, signed_inset(edge["dihedral_deg"], parameters.thickness_mm))})
        # View the opposite side of the exterior-oriented face. Reverse the
        # loop too, so clipping and labels still receive a CCW polygon. Keep
        # the first edge first; its neighbors now run in the reverse order.
        order = [1, 0] + list(range(len(face) - 1, 1, -1))
        xy[:, 0] = xy[:, 0].max() - xy[:, 0]
        xy = xy[order]
        edge_order = [0] + list(range(len(face) - 1, 0, -1))
        panel_edges = [panel_edges[i] for i in edge_order]
        for i, edge in enumerate(panel_edges):
            edge["label"] = f"E{i + 1}"
        reference = xy.tolist()
        if phase2:
            interior = offset_polygon(reference, [e["signed_inset_mm"] for e in panel_edges])
            blank = offset_polygon(reference, [min(0,e["signed_inset_mm"]) for e in panel_edges])
            if not blank:
                raise ValueError("An extended blank loses an edge. Reduce slab thickness or face offset.")
            shift = -np.array(blank).min(axis=0)
            reference = (np.array(reference)+shift).tolist()
            blank = (np.array(blank)+shift).tolist()
            interior = (np.array(interior)+shift).tolist() if interior else []
        else:
            blank = reference
            interior = inset_polygon(reference, [e["inset_mm"] for e in panel_edges])
        for i,edge in enumerate(panel_edges):
            edge["blank_length_mm"] = float(np.linalg.norm(np.array(blank[(i+1)%len(blank)])-blank[i]))
        groups[key] = {"quantity": 1, "sides": len(face), "polygon_mm": blank,
                       "reference_polygon_mm": reference, "phase2":phase2,
                       "view": "interior-up", "edges": panel_edges, "instances":[instance],
                       "inset_polygon_mm": interior, "face_ids": [fi],
                       "warnings": [] if interior else ["Bevels consume the interior face. Reduce slab thickness or increase edge length."]}
    templates = sorted(groups.values(), key=lambda t: (t["sides"], tuple(round(e["angle_deg"], 8) for e in t["edges"])))
    for i, template in enumerate(templates):
        number=i+1
        label=""
        while number:
            number,remainder=divmod(number-1,26)
            label=chr(65+remainder)+label
        template["id"] = label
        for instance in template["instances"]:
            instance["template_id"] = template["id"]
    if sum(t["quantity"] for t in templates) != len(mesh["faces"]):
        raise ValueError("Panel multiplicities do not match the source mesh.")
    warnings = [f"Template {t['id']}: {w}" for t in templates for w in t["warnings"]]
    if cut_edge < 25:
        warnings.append("Small panels may not have room for legible printed bevel labels.")
    if mesh["source"].get("chirality"):
        warnings.append("Chiral solid: preserve the displayed handedness. Templates are grouped by rotation only; do not mirror them.")
    fabrication_error = None
    thickness_check = None
    if phase2:
        try:
            thickness_check = check_thick_shell(mesh, parameters.thickness_mm, [f["id"] for f in records])
        except ValueError as error:
            fabrication_error = str(error)
            warnings.append(fabrication_error)
        if thickness_check and thickness_check["collisions"]:
            count=len(thickness_check["collisions"])
            warnings.append(f"{count} thick-panel overlaps need a closer look. Templates can be printed with marked areas and panel references for manual relief.")
        warnings.append("Construction note: a small scrap joint can help you judge the fit before making the full set.")
    collisions=thickness_check["collisions"] if thickness_check else []
    collision_annotations(mesh,templates,collisions)
    working=np.ptp(vertices,axis=0)[[0,2,1]]
    fired=working*(1-parameters.shrinkage_percent/100)
    name = construction["preset"]["name"] if phase2 and construction["preset"] else mesh["source"]["name"] + (" · modified faces" if phase2 else "")
    return {"parameters": parameters.model_dump(), "name": name,
            "geometry_version":2, "phase2":phase2, "base_faces":construction["base_faces"],
            "face_records":records, "thickness_check":thickness_check,
            "fabrication_error":fabrication_error,
            "dimensions":{"axes":["width","depth","height"],"working_mm":working.tolist(),
                          "fired_mm":fired.tolist(),"reference":"Exterior-reference bounds in model axes; ceramic results vary."},
            "chirality": mesh["source"].get("chirality"), "cut_edge_mm": cut_edge,
            "total_faces": len(mesh["faces"]), "total_edges": len(edges),
            "vertices": vertices.tolist(), "faces": mesh["faces"], "edges": edges,
            "edge_types": [{"id": i, "adjacent_sides": list(sides), "angle_deg": angle,
                            "dihedral_deg": 360-angle*2 if kind=="concave" else angle*2,
                            "edge_kind":kind,"cut_side":side} for i, (sides, angle, kind, side) in enumerate(types)],
            "templates": templates, "warnings": warnings}
