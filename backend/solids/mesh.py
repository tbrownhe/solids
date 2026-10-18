"""Oriented, closed polygon meshes; signed joints and surface intersections."""
from collections import defaultdict, deque
from math import acos, atan2, degrees

import numpy as np


def signed_joint(tangent, n1, n2):
    tangent = np.asarray(tangent, dtype=float)
    tangent /= np.linalg.norm(tangent)
    dot = float(np.clip(np.dot(n1, n2), -1, 1))
    turn = degrees(atan2(float(tangent @ np.cross(n1, n2)), dot))
    if abs(turn) < 1e-7:
        turn = 0.0
    elif abs(abs(turn) - 180) < 1e-7:
        raise ValueError("A folded-back seam has no usable miter. Reduce the face offset.")
    # acos retains the established convex numerical convention.
    magnitude = degrees(acos(dot)) if turn else 0.0
    delta = 180 - (magnitude if turn > 0 else -magnitude if turn < 0 else 0)
    return {"signed_fold_deg": turn, "dihedral_deg": delta,
            "angle_deg": min(delta, 360 - delta) / 2,
            "edge_kind": "convex" if turn > 0 else "concave" if turn < 0 else "flat",
            "cut_side": "interior" if turn >= 0 else "exterior"}


def _near_contact(point, shared, eps):
    if len(shared) == 0:
        return False
    if len(shared) == 1:
        return np.linalg.norm(point - shared[0]) <= eps
    a, b = shared[:2]
    ab = b - a
    t = float(np.clip(np.dot(point - a, ab) / np.dot(ab, ab), 0, 1))
    return np.linalg.norm(point - a - t * ab) <= eps


def _clip2(subject, clip, eps):
    cross = lambda a, b: float(a[0]*b[1] - a[1]*b[0])
    if cross(clip[1]-clip[0], clip[2]-clip[0]) < 0:
        clip = clip[::-1]
    result = list(subject)
    for a, b in zip(clip, np.roll(clip, -1, axis=0)):
        if not result:
            break
        output = []
        for p, q in zip(result, result[1:] + result[:1]):
            dp, dq = cross(b-a, p-a), cross(b-a, q-a)
            if dp >= -eps:
                output.append(p)
            if (dp > 0) != (dq > 0) and abs(dp-dq) > 1e-15:
                output.append(p + (q-p)*dp/(dp-dq))
        result = output
    return result


def _triangle_contact(a, b, shared, eps):
    """True for contacts beyond an intended common vertex or edge."""
    na = np.cross(a[1]-a[0], a[2]-a[0]); na /= np.linalg.norm(na)
    nb = np.cross(b[1]-b[0], b[2]-b[0]); nb /= np.linalg.norm(nb)
    da, db = (a-b[0]) @ nb, (b-a[0]) @ na
    if min(da) > eps or max(da) < -eps or min(db) > eps or max(db) < -eps:
        return False
    direction = np.cross(na, nb)
    if np.linalg.norm(direction) < 1e-8:
        if max(abs(db)) > eps:
            return False
        keep = [i for i in range(3) if i != int(np.argmax(abs(na)))]
        clipped = _clip2(a[:, keep], b[:, keep], eps*max(np.linalg.norm(a[1]-a[0]), 1))
        projected_shared = shared[:, keep] if len(shared) else np.empty((0, 2))
        return any(not _near_contact(p, projected_shared, eps*3) for p in clipped)
    direction /= np.linalg.norm(direction)

    def section(triangle, distances):
        points = [p for p, d in zip(triangle, distances) if abs(d) <= eps]
        for i in range(3):
            j = (i+1) % 3
            if distances[i]*distances[j] < -eps*eps:
                points.append(triangle[i] + (triangle[j]-triangle[i])*distances[i]/(distances[i]-distances[j]))
        return points

    aa, bb = section(a, da), section(b, db)
    if not aa or not bb:
        return False
    pa, pb = np.array(aa) @ direction, np.array(bb) @ direction
    low, high = max(min(pa), min(pb)), min(max(pa), max(pb))
    if high < low - eps:
        return False
    origin = aa[0]
    points = [origin + direction*(v - origin @ direction) for v in (low, high)]
    return any(not _near_contact(p, shared, eps*3) for p in points)


def check_self_intersections(vertices, faces, face_ids=None):
    """Broad-phase AABBs, then triangle contacts; adjacent overlap is not skipped."""
    vertices = np.asarray(vertices, dtype=float)
    eps = max(float(np.linalg.norm(np.ptp(vertices, axis=0)))*1e-8, 1e-8)
    triangles, owners = [], []
    for fi, face in enumerate(faces):
        for i in range(1, len(face)-1):
            triangles.append([face[0], face[i], face[i+1]])
            owners.append(fi)
    indices = np.array(triangles)
    triangles = vertices[indices]
    lows, highs = triangles.min(axis=1), triangles.max(axis=1)
    for i, a in enumerate(triangles):
        candidates = np.flatnonzero(np.all(highs[i] >= lows[i+1:] - eps, axis=1) &
                                    np.all(highs[i+1:] >= lows[i] - eps, axis=1)) + i+1
        for j in candidates:
            if owners[i] == owners[j]:
                continue
            shared_ids = sorted(set(indices[i]) & set(indices[j]))
            shared = vertices[shared_ids]
            if _triangle_contact(a, triangles[j], shared, eps):
                names = face_ids or [f"face {k+1}" for k in range(len(faces))]
                raise ValueError(f"Surface intersection between {names[owners[i]]} and {names[owners[j]]}. Reduce the face offset.")


def analyze_mesh(vertices, faces, *, face_ids=None, intersections=True):
    vertices = np.asarray(vertices, dtype=float)
    if vertices.ndim != 2 or vertices.shape[1] != 3 or not np.isfinite(vertices).all():
        raise ValueError("Invalid mesh vertices.")
    span = float(np.linalg.norm(np.ptp(vertices, axis=0)))
    eps = max(span*1e-8, 1e-9)
    faces = [list(face) for face in faces]
    normals, incidence, graph = [], defaultdict(list), defaultdict(set)
    used = set()
    volume = 0.0
    centered = vertices - vertices.mean(axis=0)
    for fi, face in enumerate(faces):
        if len(face) < 3 or len(set(face)) != len(face) or any(i < 0 or i >= len(vertices) for i in face):
            raise ValueError(f"Invalid polygon boundary at face {fi+1}.")
        p = vertices[face]
        n = np.cross(p[1]-p[0], p[2]-p[0])
        if np.linalg.norm(n) <= eps*eps:
            raise ValueError(f"Zero-area panel at face {fi+1}.")
        n /= np.linalg.norm(n)
        if max(abs((p-p[0]) @ n)) > eps:
            raise ValueError(f"Non-planar panel at face {fi+1}.")
        normals.append(n)
        used.update(face)
        for a, b in zip(face, face[1:]+face[:1]):
            length = np.linalg.norm(vertices[b]-vertices[a])
            if length <= eps:
                raise ValueError("A panel has a tiny or zero-length edge.")
            if min(np.cross(vertices[b]-vertices[a], p-vertices[a]) @ n) < -eps*length:
                raise ValueError("Each individual panel must be a simple convex polygon.")
            incidence[tuple(sorted((a,b)))].append((fi,a,b))
        q = centered[face]
        for i in range(1,len(face)-1):
            volume += float(q[0] @ np.cross(q[i],q[i+1]))/6
    if len(used) != len(vertices):
        raise ValueError("Mesh contains unused vertices.")
    if any(len(fs) != 2 for fs in incidence.values()):
        raise ValueError("Mesh is not closed: every edge must have exactly two faces.")
    edges = []
    for ei, ((a,b), fs) in enumerate(sorted(incidence.items())):
        (f1,a1,b1),(f2,a2,b2) = fs
        if (a1,b1) != (b2,a2):
            raise ValueError("Mesh faces have inconsistent winding; repair orientation before exporting.")
        graph[f1].add(f2); graph[f2].add(f1)
        joint = signed_joint(vertices[b1]-vertices[a1], normals[f1], normals[f2])
        edges.append({"id": f"J{ei+1:03d}", "vertices": [a,b], "faces": [f1,f2],
                      "length_mm": float(np.linalg.norm(vertices[b]-vertices[a])),
                      "adjacent_sides": sorted([len(faces[f1]),len(faces[f2])]), **joint})
    visited, queue = {0}, deque([0])
    while queue:
        for neighbor in graph[queue.popleft()] - visited:
            visited.add(neighbor); queue.append(neighbor)
    if len(visited) != len(faces):
        raise ValueError("Source mesh has disconnected components.")
    if len(vertices)-len(edges)+len(faces) != 2:
        raise ValueError("Mesh fails the Euler characteristic check for a closed genus-zero shell.")
    for vi in range(len(vertices)):
        around = {fi for fi,face in enumerate(faces) if vi in face}
        local = {fi: graph[fi] & around for fi in around}
        if any(len(neighbors) != 2 for neighbors in local.values()):
            raise ValueError("Nonmanifold vertex: the incident faces do not form one ring.")
        seen, pending = set(), [next(iter(around))]
        while pending:
            current = pending.pop()
            if current not in seen:
                seen.add(current); pending.extend(local[current]-seen)
        if seen != around:
            raise ValueError("Nonmanifold vertex: multiple face rings meet at one point.")
    if volume <= eps**3:
        raise ValueError("Mesh is globally inward oriented or has zero enclosed volume; reverse its winding.")
    if intersections:
        check_self_intersections(vertices, faces, face_ids)
    return {"vertices": vertices, "faces": faces, "normals": normals,
            "edges": edges, "volume_mm3": volume}
