"""Signed miter sections and conservative finite-thickness shell checks.

At inward depth s, an edge's inward in-plane coordinate is x=s*cot(delta/2).
Reflex edges have negative offsets and require an extended raw blank. All slab
material remains between the exterior reference plane and inward depth t.
"""
from itertools import combinations
from math import radians, tan

import numpy as np
from scipy.spatial import ConvexHull, QhullError


def signed_inset(delta, thickness):
    return 0.0 if abs(delta-180) < 1e-7 else thickness/tan(radians(delta/2))


def offset_polygon(polygon, offsets):
    """Shift convex supporting lines, permitting outward (negative) offsets.

    Reject topology changes rather than silently dropping an identified edge.
    """
    points = np.asarray(polygon, dtype=float)
    lines = []
    for i, a in enumerate(points):
        edge = points[(i+1) % len(points)] - a
        inward = np.array([-edge[1], edge[0]]) / np.linalg.norm(edge)
        lines.append((inward, float(inward @ a) + offsets[i]))
    corners = []
    for i in range(len(points)):
        n0,h0 = lines[i-1]; n1,h1 = lines[i]
        matrix = np.array([n0,n1])
        if abs(np.linalg.det(matrix)) < 1e-10:
            return []
        p = np.linalg.solve(matrix, [h0,h1])
        if any(n @ p < h-1e-7 for n,h in lines):
            return []
        corners.append(p)
    if any(np.linalg.norm(corners[i]-corners[i-1]) < 1e-6 for i in range(len(corners))):
        return []
    area = sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(corners,corners[1:]+corners[:1]))/2
    return [p.tolist() for p in corners] if area > 1e-6 else []


def slab_cell(points, normal, deltas, thickness):
    """Construct every vertex of a panel's bounded 3D miter half-space solid."""
    points = np.asarray(points, dtype=float)
    origin = points[0]
    u = points[1]-origin; u /= np.linalg.norm(u)
    v = np.cross(normal, u)
    xy = np.column_stack(((points-origin) @ u, (points-origin) @ v))
    planes = []
    for i, a in enumerate(xy):
        edge = xy[(i+1) % len(xy)]-a
        n = np.array([-edge[1], edge[0]])/np.linalg.norm(edge)
        planes.append([-n[0],-n[1],signed_inset(deltas[i],1),float(n @ a)])
    planes.extend([[0,0,-1,0],[0,0,1,-thickness]])
    planes = np.asarray(planes)
    vertices = []
    for ids in combinations(range(len(planes)),3):
        p = planes[list(ids)]
        if abs(np.linalg.det(p[:,:3])) < 1e-10:
            continue
        candidate = np.linalg.solve(p[:,:3],-p[:,3])
        if max(planes[:,:3] @ candidate + planes[:,3]) <= 1e-7:
            if all(np.linalg.norm(candidate-old) > 1e-6 for old in vertices):
                vertices.append(candidate)
    if len(vertices) < 4:
        raise ValueError("A thick panel collapses. Reduce slab thickness or face offset.")
    local = np.array(vertices)
    world = origin + local[:,0,None]*u + local[:,1,None]*v - local[:,2,None]*normal
    try:
        hull = ConvexHull(world)
    except QhullError as error:
        raise ValueError("A thick panel is degenerate. Reduce slab thickness or face offset.") from error
    if hull.volume < 1e-7:
        raise ValueError("A thick panel has zero volume.")
    normals = np.unique(np.round(hull.equations[:,:3],8),axis=0)
    incidence = {}
    for ti,triangle in enumerate(hull.simplices):
        for a,b in combinations(triangle,2):
            incidence.setdefault(tuple(sorted((a,b))),[]).append(ti)
    directions = []
    for (a,b),triangles in incidence.items():
        if len(triangles)==2 and np.linalg.norm(hull.equations[triangles[0],:3]-hull.equations[triangles[1],:3]) > 1e-6:
            direction = world[b]-world[a]; direction /= np.linalg.norm(direction)
            directions.append(direction)
    return {"vertices":world,"normals":normals,"directions":np.array(directions),
            "low":world.min(axis=0),"high":world.max(axis=0)}


def cells_overlap(a,b,eps):
    axes = list(a["normals"]) + list(b["normals"])
    crosses = np.cross(a["directions"][:,None,:],b["directions"][None,:,:]).reshape(-1,3)
    for axis in crosses:
        length = np.linalg.norm(axis)
        if length > 1e-8:
            axes.append(axis/length)
    axes = np.array(axes)
    aa,bb = a["vertices"] @ axes.T,b["vertices"] @ axes.T
    overlap = np.minimum(aa.max(axis=0),bb.max(axis=0))-np.maximum(aa.min(axis=0),bb.min(axis=0))
    return bool(np.all(overlap > eps))


def check_thick_shell(mesh, thickness, face_ids):
    lookup = {tuple(e["vertices"]):e for e in mesh["edges"]}
    cells=[]
    for face,normal in zip(mesh["faces"],mesh["normals"]):
        deltas=[lookup[tuple(sorted((a,b)))]["dihedral_deg"] for a,b in zip(face,face[1:]+face[:1])]
        cells.append(slab_cell(mesh["vertices"][face],normal,deltas,thickness))
    eps=max(float(np.linalg.norm(np.ptp(mesh["vertices"],axis=0)))*1e-7,1e-6)
    for i,a in enumerate(cells):
        for j in range(i+1,len(cells)):
            b=cells[j]
            if np.all(a["high"]>b["low"]+eps) and np.all(b["high"]>a["low"]+eps):
                if cells_overlap(a,b,eps):
                    raise ValueError(f"Thick clay panels {face_ids[i]} and {face_ids[j]} overlap. Reduce thickness/depth; some multi-face corners require a separate corner-relief design.")
    return {"status":"passed","panel_count":len(cells),"method":"convex miter solids / separating-axis test"}
