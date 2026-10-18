"""Orthographic assembly views of the actual reference mesh.

Occlusion is resolved in projection rather than by sorting face centres. That
keeps recesses and star points correct when their faces overlap in the drawing.
All coordinates are normalized together, so these views are never cut patterns.
"""
import numpy as np

EPS = 1e-9


def _area(polygon):
    return sum(a[0] * b[1] - a[1] * b[0]
               for a, b in zip(polygon, polygon[1:] + polygon[:1])) / 2


def _clip(polygon, normal, bias):
    """Clip a convex polygon to dot(point, normal) + bias >= 0."""
    result = []
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        da, db = a @ normal + bias, b @ normal + bias
        if da >= -EPS:
            result.append(a)
        if (da > EPS and db < -EPS) or (da < -EPS and db > EPS):
            result.append(a + (b - a) * da / (da - db))
    return result if len(result) >= 3 and abs(_area(result)) > EPS else []


def _subtract(polygon, occluder):
    """Partition the part outside a convex occluder into convex polygons."""
    outside, remaining = [], polygon
    for a, b in zip(occluder, occluder[1:] + occluder[:1]):
        normal = np.array([a[1] - b[1], b[0] - a[0]])
        bias = -a @ normal
        fragment = _clip(remaining, -normal, -bias)
        if fragment:
            outside.append(fragment)
        remaining = _clip(remaining, normal, bias)
        if not remaining:
            break
    return outside


def _edge_interval(a, b, polygon):
    low, high = 0., 1.
    for p, q in zip(polygon, polygon[1:] + polygon[:1]):
        normal = np.array([p[1] - q[1], q[0] - p[0]])
        start, change = (a - p) @ normal, (b - a) @ normal
        if abs(change) < EPS:
            if start < -EPS:
                return None
        elif change > 0:
            low = max(low, -start / change)
        else:
            high = min(high, -start / change)
    return (low, high) if high - low > EPS else None


def view_direction(design):
    """Give individually edited faces priority over the default viewing angle."""
    edited = design["parameters"].get("face_transforms", {})
    if not edited:
        modified = [f["id"] for f in design["base_faces"] if f["transform"]["mode"] != "flat"]
        if 0 < len(modified) < len(design["base_faces"]):
            edited = dict.fromkeys(modified)
    if not edited:
        return np.array([1.4, 1.1, 1.8])
    source = next(iter(sorted(edited)))
    vertices = np.asarray(design["vertices"])
    normal = np.zeros(3)
    for face, record in zip(design["faces"], design["face_records"]):
        if record["source_face_id"] == source:
            points = vertices[face]
            for a, b in zip(points[1:-1], points[2:]):
                normal += np.cross(a - points[0], b - points[0])
    normal /= np.linalg.norm(normal)
    axis = np.eye(3)[np.argmin(abs(normal))]
    right = np.cross(axis, normal)
    right /= np.linalg.norm(right)
    up = np.cross(normal, right)
    return normal + .32 * right + .24 * up


def project_schematic(design, direction):
    """Return visible surface regions and real edge segments (no hidden lines)."""
    toward = np.array(direction, dtype=float)
    toward /= np.linalg.norm(toward)
    vertical = np.array([0., 1., 0.])
    if abs(vertical @ toward) > .99:
        vertical = np.array([0., 0., 1.])
    right = np.cross(vertical, toward)
    right /= np.linalg.norm(right)
    up = np.cross(toward, right)
    vertices = np.asarray(design["vertices"], dtype=float)
    vertices = (vertices - vertices.mean(axis=0)) / np.ptp(vertices, axis=0).max()
    projected = vertices @ np.array([right, up, toward]).T
    candidates = []
    for index, face in enumerate(design["faces"]):
        points = projected[face]
        normal = np.cross(points[1] - points[0], points[2] - points[0])
        if normal[2] <= EPS:
            continue
        # z = plane.x * x + plane.y * y + plane.constant
        plane = np.array([-normal[0], -normal[1], normal @ points[0]]) / normal[2]
        polygon = list(points[:, :2])
        candidates.append({"face_index": index, "polygon": polygon, "plane": plane,
                           "bounds": (points[:, :2].min(axis=0), points[:, :2].max(axis=0))})
    visible = []
    for face in candidates:
        regions = [face["polygon"]]
        for other in candidates:
            if face is other:
                continue
            if np.any(face["bounds"][1] <= other["bounds"][0] + EPS) or np.any(other["bounds"][1] <= face["bounds"][0] + EPS):
                continue
            difference = other["plane"] - face["plane"]
            # Coplanar neighbors must not erase one another.
            if max(p @ difference[:2] + difference[2] for p in other["polygon"]) <= EPS:
                continue
            nearer = _clip(other["polygon"], difference[:2], difference[2] - EPS)
            if nearer:
                regions = [part for region in regions for part in _subtract(region, nearer)]
            if not regions:
                break
        if regions:
            visible.append({**face, "regions": regions})
    by_face = {face["face_index"]: face for face in visible}
    edges = []
    for edge in design["edges"]:
        a, b = projected[edge["vertices"], :2]
        intervals = []
        for index in edge["faces"]:
            for region in by_face.get(index, {}).get("regions", []):
                interval = _edge_interval(a, b, region)
                if interval:
                    intervals.append(interval)
        merged = []
        for low, high in sorted(intervals):
            if merged and low <= merged[-1][1] + EPS:
                merged[-1][1] = max(merged[-1][1], high)
            else:
                merged.append([low, high])
        for low, high in merged:
            edges.append([a + (b - a) * low, a + (b - a) * high])
    return {"faces": visible, "edges": edges, "vertices": projected[:, :2],
            "bounds": (projected[:, :2].min(axis=0), projected[:, :2].max(axis=0))}
