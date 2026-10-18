"""Native polygon meshes for the 13 Archimedean and five Platonic solids.

These are original mathematical constructions, not imported mesh assets. The
reflection-group construction follows H. S. M. Coxeter, "Wythoff's Construction
for Uniform Polytopes" (1935), https://doi.org/10.1112/plms/s2-38.1.327.
The snubs use the proper rotation subgroup and an equal-edge seed, as described
by Koca, Koca and Al-Shu'eili, "Chiral Polyhedra Derived From Coxeter Diagrams
and Quaternions" (2010), sections 5–6, https://arxiv.org/abs/1006.3149.
No third-party coordinate tables, face lists, or executable code are copied.

Coordinates are centered at the origin with unit edge length. Faces are true
polygon boundaries, ordered counterclockwise as seen from outside. Snubs have
one deterministic handedness; reflecting one coordinate gives the other hand.
"""

from collections import Counter
from itertools import combinations
from math import cos, pi

import numpy as np
from scipy.optimize import root
from scipy.spatial import ConvexHull


def _mirrors(p: int, q: int = 3) -> tuple[np.ndarray, list[np.ndarray]]:
    """Unit normals with Coxeter Gram matrix for the spherical triangle."""
    gram = np.array([
        [1.0, -cos(pi / p), 0.0],
        [-cos(pi / p), 1.0, -cos(pi / q)],
        [0.0, -cos(pi / q), 1.0],
    ])
    normals = np.linalg.cholesky(gram)
    reflections = [np.eye(3) - 2 * np.outer(n, n) for n in normals]
    return normals, reflections


def _orbit(seed: np.ndarray, generators: list[np.ndarray]) -> np.ndarray:
    """Enumerate a finite orbit, merging floating-point reflection noise."""
    seed = seed / np.linalg.norm(seed)
    points = [seed]
    seen = {tuple(np.round(seed, 10))}
    index = 0
    while index < len(points):
        point = points[index]
        index += 1
        for generator in generators:
            reflected = generator @ point
            key = tuple(np.round(reflected, 10))
            if key not in seen:
                seen.add(key)
                points.append(reflected)
        if len(points) > 120:
            raise RuntimeError("Coxeter orbit failed to close")
    # Sorting rounded coordinates also gives stable vertex/face IDs on restarts.
    return np.array(sorted(tuple(np.round(point, 12)) for point in points))


def _wythoff(p: int, active: tuple[int, int, int]) -> np.ndarray:
    normals, reflections = _mirrors(p)
    # Distance zero fixes a mirror; equal positive distances give equal edges.
    seed = np.linalg.solve(normals, np.array(active, dtype=float))
    return _orbit(seed, reflections)


def _snub(p: int) -> np.ndarray:
    normals, reflections = _mirrors(p)
    rotations = [reflections[i] @ reflections[j]
                 for i, j in combinations(range(3), 2)]

    def constraints(point: np.ndarray) -> np.ndarray:
        lengths = [np.sum((rotation @ point - point) ** 2)
                   for rotation in rotations]
        return np.array([lengths[0] - lengths[1],
                         lengths[0] - lengths[2],
                         np.dot(point, point) - 1.0])

    seed = np.linalg.solve(normals, np.ones(3))
    result = root(constraints, seed / np.linalg.norm(seed), tol=1e-12)
    if np.max(np.abs(constraints(result.x))) > 1e-10 or np.any(normals @ result.x <= 0):
        raise RuntimeError("Could not construct a uniform snub seed")
    return _orbit(result.x, rotations)


def _polygon_faces(vertices: np.ndarray) -> list[list[int]]:
    """Merge coplanar Qhull triangles, then order each actual polygon boundary."""
    hull = ConvexHull(vertices)
    planes: dict[tuple[float, ...], tuple[np.ndarray, set[int]]] = {}
    for triangle, equation in zip(hull.simplices, hull.equations, strict=True):
        key = tuple(np.round(equation, 8))
        if key not in planes:
            planes[key] = (equation[:3], set())
        planes[key][1].update(int(i) for i in triangle)

    faces = []
    for normal, indices in planes.values():
        indices = sorted(indices)
        points = vertices[indices]
        center = points.mean(axis=0)
        u = points[0] - center
        u /= np.linalg.norm(u)
        v = np.cross(normal, u)
        angles = np.arctan2((points - center) @ v, (points - center) @ u)
        face = [indices[i] for i in np.argsort(angles)]
        start = face.index(min(face))
        faces.append(face[start:] + face[:start])
    return sorted(faces, key=lambda face: (len(face), face))


def _build(solid_id: str, name: str, family: str, vertices: np.ndarray,
           expected: dict[int, int], *, chiral: bool = False) -> dict:
    faces = _polygon_faces(vertices)
    counts = dict(Counter(map(len, faces)))
    if counts != expected:
        raise RuntimeError(f"Invalid polygon inventory for {solid_id}: {counts}")
    edges = {tuple(sorted((face[i], face[(i + 1) % len(face)])))
             for face in faces for i in range(len(face))}
    lengths = np.array([np.linalg.norm(vertices[a] - vertices[b]) for a, b in edges])
    if np.ptp(lengths) > 1e-8:
        raise RuntimeError(f"Nonuniform edges for {solid_id}")
    if len(vertices) - len(edges) + len(faces) != 2:
        raise RuntimeError(f"Invalid topology for {solid_id}")
    vertices = vertices / lengths.mean()
    result = {
        "id": solid_id,
        "name": name,
        "family": family,
        "vertices": vertices.tolist(),
        "faces": faces,
        "vertex_count": len(vertices),
        "edge_count": len(edges),
        "face_count": len(faces),
        "face_types": {str(sides): count for sides, count in sorted(counts.items())},
    }
    if chiral:
        result["chirality"] = "One handedness; mirror image not included"
    return result


# p, active mirrors, and expected actual polygon inventories.
_DEFINITIONS = [
    ("tetrahedron", "Tetrahedron", "Platonic", 3, (1, 0, 0), {3: 4}),
    ("cube", "Cube", "Platonic", 4, (1, 0, 0), {4: 6}),
    ("octahedron", "Octahedron", "Platonic", 4, (0, 0, 1), {3: 8}),
    ("dodecahedron", "Dodecahedron", "Platonic", 5, (1, 0, 0), {5: 12}),
    ("icosahedron", "Icosahedron", "Platonic", 5, (0, 0, 1), {3: 20}),
    ("truncated-tetrahedron", "Truncated tetrahedron", "Archimedean", 3, (1, 1, 0), {3: 4, 6: 4}),
    ("cuboctahedron", "Cuboctahedron", "Archimedean", 4, (0, 1, 0), {3: 8, 4: 6}),
    ("truncated-cube", "Truncated cube", "Archimedean", 4, (1, 1, 0), {3: 8, 8: 6}),
    ("truncated-octahedron", "Truncated octahedron", "Archimedean", 4, (0, 1, 1), {4: 6, 6: 8}),
    ("rhombicuboctahedron", "Rhombicuboctahedron", "Archimedean", 4, (1, 0, 1), {3: 8, 4: 18}),
    ("truncated-cuboctahedron", "Truncated cuboctahedron", "Archimedean", 4, (1, 1, 1), {4: 12, 6: 8, 8: 6}),
    ("snub-cube", "Snub cube", "Archimedean", 4, None, {3: 32, 4: 6}),
    ("icosidodecahedron", "Icosidodecahedron", "Archimedean", 5, (0, 1, 0), {3: 20, 5: 12}),
    ("truncated-dodecahedron", "Truncated dodecahedron", "Archimedean", 5, (1, 1, 0), {3: 20, 10: 12}),
    ("truncated-icosahedron", "Truncated icosahedron", "Archimedean", 5, (0, 1, 1), {5: 12, 6: 20}),
    ("rhombicosidodecahedron", "Rhombicosidodecahedron", "Archimedean", 5, (1, 0, 1), {3: 20, 4: 30, 5: 12}),
    ("truncated-icosidodecahedron", "Truncated icosidodecahedron", "Archimedean", 5, (1, 1, 1), {4: 30, 6: 20, 10: 12}),
    ("snub-dodecahedron", "Snub dodecahedron", "Archimedean", 5, None, {3: 80, 5: 12}),
]

SOLIDS = {
    solid_id: _build(solid_id, name, family,
                     _snub(p) if active is None else _wythoff(p, active),
                     expected, chiral=active is None)
    for solid_id, name, family, p, active, expected in _DEFINITIONS
}


def get_solid(solid_id: str) -> dict:
    """Return a native mesh; an unknown ID raises KeyError."""
    return SOLIDS[solid_id]


def list_solids() -> list[dict]:
    """Return small public catalog entries without coordinate arrays."""
    return [{key: value for key, value in solid.items() if key not in {"vertices", "faces"}}
            for solid in SOLIDS.values()]
