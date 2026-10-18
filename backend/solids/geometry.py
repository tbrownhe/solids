"""Validated convex polygon topology, symmetric inward miters, and panel grouping.

Flat coordinates are millimetres of the full exterior footprint, viewed with
the INTERIOR UP and EXTERIOR DOWN for cutting and beveling. Mesh winding is
outward. Grouping uses exterior patterns and rotations only; each grouped panel
is then viewed from its interior, reversing its displayed edge order exactly
once. This viewing reflection does not merge handed patterns or reflect the solid.
"""
from collections import defaultdict, deque
from functools import lru_cache
from math import acos, degrees, tan, radians
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from .registry import get_solid


class Parameters(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    solid_id: str = "rhombicuboctahedron"
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
    if not np.isfinite(vertices).all() or vertices.ndim != 2 or vertices.shape[1] != 3:
        raise ValueError("Invalid source vertices.")
    vertices = vertices - vertices.mean(axis=0)
    faces, normals = [], []
    adjacency = defaultdict(list)
    for raw_face in source["faces"]:
        face = list(raw_face)
        if len(face) < 3 or len(set(face)) != len(face):
            raise ValueError("Invalid polygon face.")
        points = vertices[face]
        normal = _unit(np.cross(points[1] - points[0], points[2] - points[0]))
        if np.dot(normal, points.mean(axis=0)) < 0:
            face.reverse()
            points = vertices[face]
            normal = -normal
        if np.max(np.abs((points - points[0]) @ normal)) > 1e-6:
            raise ValueError("Source mesh has a non-planar face.")
        if np.max((vertices - points[0]) @ normal) > 1e-6:
            raise ValueError("Only convex meshes are supported.")
        fi = len(faces)
        for a, b in zip(face, face[1:] + face[:1]):
            adjacency[tuple(sorted((a, b)))].append((fi, a, b))
        faces.append(face)
        normals.append(normal)
    if any(len(incidents) != 2 for incidents in adjacency.values()):
        raise ValueError("Mesh is not closed: every edge must have exactly two faces.")
    if len(vertices) - len(adjacency) + len(faces) != 2:
        raise ValueError("Mesh fails the Euler characteristic check.")
    graph = defaultdict(set)
    edges = []
    for (a, b), incidents in sorted(adjacency.items()):
        (f1, a1, b1), (f2, a2, b2) = incidents
        if a1 != b2 or b1 != a2:
            raise ValueError("Mesh faces have inconsistent orientation.")
        graph[f1].add(f2)
        graph[f2].add(f1)
        alpha = degrees(acos(float(np.clip(np.dot(normals[f1], normals[f2]), -1, 1))))
        if not 0 < alpha < 180:
            raise ValueError("Coplanar or degenerate source face adjacency.")
        edges.append({"vertices": [a, b], "faces": [f1, f2],
                      "angle_deg": (180 - alpha) / 2, "dihedral_deg": 180 - alpha,
                      "adjacent_sides": sorted([len(faces[f1]), len(faces[f2])])})
    visited, queue = {0}, deque([0])
    while queue:
        for neighbor in graph[queue.popleft()] - visited:
            visited.add(neighbor)
            queue.append(neighbor)
    if len(visited) != len(faces):
        raise ValueError("Source mesh has disconnected components.")
    lengths = [float(np.linalg.norm(vertices[a] - vertices[b])) for a, b in adjacency]
    edge_length = float(np.mean(lengths))
    if max(lengths) - min(lengths) > edge_length * 1e-6:
        raise ValueError("Source mesh does not have uniform exterior edges.")
    vertices /= edge_length
    return {"source": source, "vertices": vertices, "faces": faces,
            "normals": normals, "edges": edges}


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


def make_design(parameters: Parameters) -> dict:
    mesh = topology(parameters.solid_id)
    cut_edge = parameters.edge_length_mm / (1 - parameters.shrinkage_percent / 100)
    if cut_edge > 5000:
        raise ValueError("Shrinkage compensation exceeds the 5,000 mm working-edge limit.")
    vertices = mesh["vertices"] * cut_edge
    edges = [dict(edge) for edge in mesh["edges"]]
    edge_lookup = {tuple(edge["vertices"]): edge for edge in edges}
    types = sorted({(tuple(e["adjacent_sides"]), round(e["angle_deg"], 8)) for e in edges})
    for edge in edges:
        edge["category"] = types.index((tuple(edge["adjacent_sides"]), round(edge["angle_deg"], 8)))
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
                             round(edge["angle_deg"], 8), len(mesh["faces"][neighbor])))
        start = min(range(len(sequence)), key=lambda i: tuple(sequence[i:] + sequence[:i]))
        key = tuple(sequence[start:] + sequence[:start])
        if key in groups:
            groups[key]["quantity"] += 1
            groups[key]["face_ids"].append(fi)
            continue
        face = raw_face[start:] + raw_face[:start]
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
                                "inset_mm": parameters.thickness_mm / tan(radians(edge["angle_deg"]))})
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
        interior = inset_polygon(xy.tolist(), [e["inset_mm"] for e in panel_edges])
        groups[key] = {"quantity": 1, "sides": len(face), "polygon_mm": xy.tolist(),
                       "view": "interior-up", "edges": panel_edges,
                       "inset_polygon_mm": interior, "face_ids": [fi],
                       "warnings": [] if interior else ["Bevels consume the interior face. Reduce slab thickness or increase edge length."]}
    templates = sorted(groups.values(), key=lambda t: (t["sides"], tuple(round(e["angle_deg"], 8) for e in t["edges"])))
    for i, template in enumerate(templates):
        template["id"] = chr(65 + i)
    if sum(t["quantity"] for t in templates) != len(mesh["faces"]):
        raise ValueError("Panel multiplicities do not match the source mesh.")
    warnings = [f"Template {t['id']}: {w}" for t in templates for w in t["warnings"]]
    if cut_edge < 25:
        warnings.append("Small panels may not have room for legible printed bevel labels.")
    if mesh["source"].get("chirality"):
        warnings.append("Chiral solid: preserve the displayed handedness. Templates are grouped by rotation only; do not mirror them.")
    return {"parameters": parameters.model_dump(), "name": mesh["source"]["name"],
            "chirality": mesh["source"].get("chirality"), "cut_edge_mm": cut_edge,
            "total_faces": len(mesh["faces"]), "total_edges": len(edges),
            "vertices": vertices.tolist(), "faces": mesh["faces"], "edges": edges,
            "edge_types": [{"id": i, "adjacent_sides": list(sides), "angle_deg": angle,
                            "dihedral_deg": angle * 2} for i, (sides, angle) in enumerate(types)],
            "templates": templates, "warnings": warnings}
