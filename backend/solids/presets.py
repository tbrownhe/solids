"""Construction metadata shared by geometry and the lightweight usage reporter."""

SUPPORTED_BASES = {"cube","tetrahedron","octahedron","cuboctahedron","rhombicuboctahedron","dodecahedron"}
PRESETS = [
    {"id":"excavated-cube-single","name":"Cube · one recessed face","solid_id":"cube","mode":"inward","scope":"one"},
    {"id":"excavated-cube","name":"Excavated cube","solid_id":"cube","mode":"inward","scope":"all"},
    {"id":"excavated-tetrahedron","name":"Excavated tetrahedron","solid_id":"tetrahedron","mode":"inward","scope":"all"},
    {"id":"excavated-octahedron","name":"Excavated octahedron","solid_id":"octahedron","mode":"inward","scope":"all"},
    {"id":"stellated-cube","name":"Outward-stellated cube","solid_id":"cube","mode":"outward","scope":"all"},
    {"id":"stellated-octahedron","name":"Outward-stellated octahedron","solid_id":"octahedron","mode":"outward","scope":"all"},
    {"id":"stellated-dodecahedron","name":"Outward-stellated dodecahedron","solid_id":"dodecahedron","mode":"outward","scope":"all"},
]
